# Notification Gateway

A backend service that accepts notification requests, protects itself with authentication and rate limiting, and delivers them asynchronously in the background with automatic retries.

Built with **FastAPI, PostgreSQL, Redis, Celery, and Docker**.

---

## Why this exists

If every part of an application sends notifications (SMS, email, push) directly, a slow or failing provider blocks the request that triggered it. A checkout can hang because an SMS API is slow.

This service sits in front of that problem:

1. A client sends `POST /notify` with a valid token.
2. The API checks who is asking and whether they are sending too much.
3. The request is saved to the database and a job is queued.
4. The API responds immediately with `{"status": "pending"}`.
5. A separate worker picks up the job, delivers it, retries on failure, and updates the status.
6. The client can check the result anytime with `GET /status/{id}`.

The slow, unreliable part (delivery) never blocks the fast part (accepting the request).

---

## Architecture

```
                 ┌──────────────────────────────┐
  Client ──────► │  FastAPI  (JWT auth)         │
                 │   - /signup /login /refresh  │
                 │   - /notify  /status/{id}    │
                 └───────┬───────────┬──────────┘
                         │           │
            rate limit   │           │  write request (status: pending)
            check        ▼           ▼
                    ┌────────┐  ┌────────────┐
                    │ Redis  │  │ PostgreSQL │
                    └───┬────┘  └─────▲──────┘
                        │ job queue   │ update status
                        ▼             │
                 ┌──────────────────────────────┐
                 │  Celery worker               │
                 │   - sends notification       │
                 │   - retries with backoff     │
                 │   - marks sent / failed      │
                 └──────────────────────────────┘
```

---

## Features

**Authentication**
- Signup and login with bcrypt-hashed passwords
- JWT access tokens (15 min) and refresh tokens (7 days)
- Protected routes via a reusable FastAPI dependency
- Generic login error message to avoid leaking which emails are registered

**Authorization**
- Users can only read the status of their own notifications (`403` otherwise)

**Rate limiting**
- Sliding-window limiter on `/notify`, implemented with Redis sorted sets
- Default: 5 requests per 60 seconds per user, returns `429` when exceeded
- Sliding window avoids the burst-at-boundary flaw of fixed-window counters

**Asynchronous processing**
- `/notify` returns immediately; delivery happens in a Celery worker
- Email delivery through an SMTP sandbox (Mailtrap); SMS and push are mocked

**Reliability**
- Up to 3 retries with exponential backoff (1s, 2s, 4s)
- Notification is marked `failed` after retries are exhausted, with the attempt count stored in `retry_count`
- Idempotency check: a task skips notifications that are already `sent` or `failed`, so a duplicate message does not send twice

**Deployment**
- Separate Dockerfiles for the API and the worker
- `docker-compose.yml` for running the API, worker, and Redis together
- Deployed on Railway with managed PostgreSQL and Redis

---

## Tech stack

| Layer | Tool |
|---|---|
| Language | Python |
| API framework | FastAPI, Uvicorn |
| Validation | Pydantic |
| Database | PostgreSQL, SQLAlchemy |
| Auth | python-jose (JWT), passlib (bcrypt) |
| Cache / rate limiting / broker | Redis |
| Background jobs | Celery |
| Containers | Docker, Docker Compose |
| Hosting | Railway |
| Load testing | Locust |

---

## API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/signup` | No | Create an account |
| POST | `/login` | No | Returns access and refresh tokens |
| POST | `/refresh` | No | Exchange a refresh token for a new access token |
| GET | `/me` | Yes | Returns the current user |
| POST | `/notify` | Yes | Queue a notification (rate limited) |
| GET | `/status/{id}` | Yes | Check a notification's status (owner only) |
| GET | `/health` | No | Health check |

Interactive docs are available at `/docs` when the server is running.

### Notification statuses

`pending` → `sent`, or `pending` → `failed` after retries are exhausted.

### Example

```bash
# 1. Sign up
curl -X POST http://localhost:8000/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "yourpassword"}'

# 2. Log in (returns access_token and refresh_token)
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "yourpassword"}'

# 3. Send a notification
curl -X POST http://localhost:8000/notify \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"type": "email", "recipient": "someone@example.com", "content": "Your order is confirmed"}'
# -> {"id": 12, "status": "pending"}

# 4. Check status
curl http://localhost:8000/status/12 \
  -H "Authorization: Bearer <access_token>"
# -> {"id": 12, "status": "sent"}
```

`type` must be one of `email`, `sms`, or `push`.

On Windows PowerShell, use `curl.exe` instead of `curl`.

---

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis (or Docker)
- Docker Desktop (for the containerized setup)

### Run locally

```bash
git clone https://github.com/Avinash-475/notification-gateway.git
cd notification-gateway

python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create the database:

```sql
CREATE DATABASE notification_gateway_db;
```

Create the tables (see the schema section below), then start Redis, the API, and the worker in separate terminals:

```bash
# Redis
docker run -d -p 6379:6379 redis

# API
uvicorn main:app --reload

# Worker (the --pool=solo flag is needed on Windows)
celery -A celery_app worker --loglevel=info --pool=solo
```

### Run with Docker Compose

```bash
docker-compose up --build
```

This starts the API, the worker, and Redis. PostgreSQL is expected to be reachable from the containers (the compose file points at the host machine through `host.docker.internal`).

### Configuration

| Variable | Purpose | Default (local) |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:<password>@localhost:5432/notification_gateway_db` |
| `REDIS_URL` | Redis connection string for the broker and result backend | `redis://localhost:6379/0` |

Set real values for the JWT secret key and SMTP credentials before any real deployment. Do not commit secrets.

---

## Database schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE notification_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(50) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Project structure

```
notification-gateway/
├── main.py              # FastAPI app and endpoints
├── auth.py              # Password hashing, JWT creation, auth dependency
├── database.py          # SQLAlchemy engine and session
├── models.py            # SQLAlchemy models
├── rate_limiter.py      # Redis sliding-window rate limiter
├── celery_app.py        # Celery app and notification task
├── Dockerfile           # API image
├── Dockerfile.worker    # Worker image
├── docker-compose.yml   # API + worker + Redis
├── locustfile.py        # Load test scenario
└── requirements.txt
```

---

## Design decisions

**Why a queue instead of sending inline.** Accepting a request and delivering it have very different latency and failure profiles. Separating them means a slow provider cannot slow the API.

**Why a sliding window rate limiter.** A fixed window resets on the clock, so a user can send a full quota just before the reset and another full quota just after, doubling the effective rate for a moment. A sliding window stores each request's timestamp in a Redis sorted set and always counts the last N seconds from now, so there is no boundary to exploit.

**Why bcrypt and HMAC-signed JWTs are separate.** Passwords need a deliberately slow, irreversible hash. Tokens need fast verification on every request and a payload the server can read back. They solve different problems and use different algorithms.

**Why status-based idempotency.** Retries and duplicate queue messages can run the same task twice. Checking the stored status before sending prevents a second delivery.

---

## Testing

- `test_flow.py` runs signup, login, notify, and status in sequence.
- `test_rate_limiter.py` exercises the rate limiter in isolation.
- Retry behavior can be exercised by sending a notification with the content `FORCE_FAIL`, which makes the worker fail deliberately. Remove this hook before using the service for anything real.

### Load testing

Load tested with Locust against a local instance.

**Verified:** with two concurrent simulated users, each user received `200` for their first 5 requests and `429` after that, then `200` again as the sliding window moved forward. The rate limiter enforces its limit correctly under concurrent traffic.

**Results (fill in after the final run):**

| Metric | Before optimization | After optimization |
|---|---|---|
| Users | | |
| /notify median latency | | |
| /notify 95th percentile | | |
| /notify failure rate | | |
| Change made | | |

---

## Known limitations and next steps

- **Idempotency race.** The status check is not atomic. Two workers reading `pending` at the same instant could both send. The fix is an atomic claim (`UPDATE ... WHERE status = 'pending'`) or a Redis lock.
- **Secrets in code.** The JWT secret and SMTP credentials should come from environment variables, not source files.
- **Refresh tokens are not revocable.** They are stateless JWTs, so logout does not invalidate them.
- **SMS and push are mocked.** Only email goes through a real (sandbox) provider.
- **No database migrations.** Tables are created by hand; Alembic would be the next step.
- **Connection pooling.** Pool size and overflow should be tuned and validated under load.

---

## Author

**Avinash S** — [GitHub](https://github.com/Avinash-475)
