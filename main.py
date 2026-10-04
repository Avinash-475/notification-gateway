from dotenv import load_dotenv
load_dotenv()

from typing import Literal
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from jose import JWTError, jwt

from database import SessionLocal
from models import User
from models import NotificationRequest as NotificationDB
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user_email,
    SECRET_KEY,
    ALGORITHM,
)
from rate_limiter import is_rate_limited
from celery_app import send_notification_task

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok.."}


@app.get("/greet/{name}")
def greet(name: str):
    return {"message": f"Hello, {name}"}


@app.get("/multi/{a}/{b}")
def mul(a: int, b: int):
    return {"mulltiplication": a * b}


class SignupRequest(BaseModel):
    email: str
    password: str


@app.post("/signup")
def signup(request: SignupRequest):
    db = SessionLocal()

    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=request.email,
        hashed_password=hash_password(request.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()

    return {"id": new_user.id, "email": new_user.email}


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/login")
def login(request: LoginRequest):
    db = SessionLocal()

    user = db.query(User).filter(User.email == request.email).first()
    db.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/refresh")
def refresh(request: RefreshRequest):
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = create_access_token(data={"sub": email})
    return {"access_token": new_access_token, "token_type": "bearer"}


@app.get("/me")
def read_current_user(current_user_email: str = Depends(get_current_user_email)):
    return {"email": current_user_email}


class NotificationRequest(BaseModel):
    type: Literal["sms", "push", "email"]
    recipient: str
    content: str


@app.post("/notify")
def notify(
    request: NotificationRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    db = SessionLocal()
    current_user = db.query(User).filter(User.email == current_user_email).first()

    if is_rate_limited(current_user.id):
        db.close()
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    new_notification = NotificationDB(
        user_id=current_user.id,
        type=request.type,
        recipient=request.recipient,
        content=request.content,
        status="pending"
    )
    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)

    send_notification_task.delay(new_notification.id)

    db.close()

    return {
        "id": new_notification.id,
        "status": new_notification.status
    }


@app.get("/status/{request_id}")
def status(request_id: int, current_user_email: str = Depends(get_current_user_email)):
    db = SessionLocal()

    current_user = db.query(User).filter(User.email == current_user_email).first()
    notification = db.query(NotificationDB).filter(NotificationDB.id == request_id).first()
    db.close()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this notification")

    return {
        "id": notification.id,
        "status": notification.status
    }