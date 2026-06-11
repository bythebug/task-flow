# task-flow

A production-ready REST API for task management built with Flask. Supports user authentication, full task CRUD, fine-grained permission sharing, Redis caching, and Docker deployment.

---

## Features

- **JWT Authentication** — register, login, logout with bcrypt password hashing
- **Task CRUD** — create, read, update, delete tasks with status and priority
- **Permission Sharing** — share tasks with view / edit / delete access levels
- **Redis Caching** — task list cached per user with automatic invalidation
- **Input Validation** — email format, password complexity, field sanitisation
- **Centralised Error Handling** — consistent JSON error responses across all endpoints
- **Docker Ready** — Dockerfile + docker-compose for one-command local setup

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | Flask 3 |
| ORM | SQLAlchemy 2 |
| Database | PostgreSQL 16 (SQLite for tests) |
| Cache | Redis 7 |
| Auth | PyJWT + bcrypt |
| Server | Gunicorn |
| Tests | pytest (66 tests) |
| Container | Docker + Docker Compose |

## Project Structure

```
task-flow/
├── app/
│   ├── __init__.py          # create_app() factory
│   ├── config.py            # JWT settings
│   ├── models.py            # SQLAlchemy models
│   ├── auth/
│   │   ├── routes.py        # /auth/* endpoints
│   │   └── service.py       # register, login, token helpers
│   ├── tasks/
│   │   ├── routes.py        # /tasks/* endpoints
│   │   ├── service.py       # permission logic
│   │   └── cache.py         # Redis helpers
│   └── core/
│       ├── database.py      # engine factory, query timing
│       ├── middleware.py    # require_auth, handle_errors decorators
│       ├── validators.py    # input validation
│       └── error_handlers.py
├── tests/                   # 66 pytest tests
├── Dockerfile
├── docker-compose.yml
├── run.py                   # gunicorn entry point
├── schema.sql               # raw DDL
└── requirements.txt
```

---

## Live Demo

**Base URL:** `https://task-flow-production-ac25.up.railway.app`

```bash
# Health check
curl https://task-flow-production-ac25.up.railway.app/health

# Register and get a token
curl -X POST https://task-flow-production-ac25.up.railway.app/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"Password123"}'
```

Import [`postman_collection.json`](postman_collection.json) into Postman for a one-click interactive tour of all endpoints — the collection auto-saves your token after login.

---

## Quick Start (Docker)

```bash
git clone https://github.com/bythebug/task-flow.git
cd task-flow
cp .env.example .env          # edit JWT_SECRET_KEY
docker compose up --build
```

API available at `http://localhost:5000`.

---

## Local Development

### Prerequisites

- Python 3.13
- PostgreSQL 16 (or use Docker)
- Redis 7 (or use Docker)

### Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/bythebug/task-flow.git
cd task-flow
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start infrastructure (PostgreSQL + Redis)
docker compose up postgres redis -d

# 4. Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY and DATABASE_URL

# 5. Run the app
python run.py
```

---

## Running Tests

```bash
# All 66 tests
pytest

# With verbose output
pytest -v

# Single test file
pytest tests/test_auth.py -v
```

Tests use SQLite in-memory and fakeredis — no external services needed.

---

## API Overview

See [API_DOCS.md](API_DOCS.md) for full request/response examples.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| POST | `/auth/logout` | Revoke token |

### Tasks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tasks/` | List tasks (paginated, filterable) |
| POST | `/tasks/` | Create task |
| GET | `/tasks/{id}` | Fetch task |
| PUT | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |

### Sharing

| Method | Endpoint | Description |
|---|---|---|
| POST | `/tasks/{id}/share` | Share with a user |
| GET | `/tasks/{id}/collaborators` | List collaborators |
| DELETE | `/tasks/{id}/share/{user_id}` | Revoke access |
| PUT | `/tasks/{id}/permissions/{user_id}` | Update permission level |

---

## Authentication

All task endpoints require a Bearer token in the `Authorization` header.

```bash
# 1. Register
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "Password123"}'

# 2. Login
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "Password123"}'
# → {"token": "eyJ...", "expires_in": 86400}

# 3. Use token
curl http://localhost:5000/tasks/ \
  -H "Authorization: Bearer eyJ..."
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///taskflow.db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Secret for signing tokens (**change this**) | dev value |
| `TOKEN_EXPIRY_HOURS` | Token lifetime in hours | `24` |
| `FLASK_ENV` | `development` or `production` | `development` |

---

## Database Setup

```bash
# With Docker (recommended)
docker compose up postgres -d

# Manual PostgreSQL
createdb taskflow
psql taskflow < schema.sql
```

---

## Troubleshooting

**`ModuleNotFoundError`** — activate the virtual environment: `source venv/bin/activate`

**`Connection refused` on PostgreSQL** — check `docker compose up postgres -d` is running

**`Token has expired`** — re-login to get a fresh token; tokens expire after 24 hours

**`401 Missing or invalid Authorization header`** — include `Authorization: Bearer <token>` in every request

**Redis unavailable** — the app continues to work; caching is silently skipped (graceful degradation)
