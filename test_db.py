from database import SessionLocal
from models import User

# Create a session (a "conversation" with the DB)
db = SessionLocal()

# Insert a test user
new_user = User(email="test@example.com", hashed_password="fakehash123")
db.add(new_user)
db.commit()
db.refresh(new_user)

print(f"Inserted user with id: {new_user.id}")

# Read it back
fetched_user = db.query(User).filter(User.email == "test@example.com").first()
print(f"Fetched user: {fetched_user.email}, created at: {fetched_user.created_at}")

db.close()