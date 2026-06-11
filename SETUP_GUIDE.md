# Setup Guide

Step-by-step instructions for running task-flow locally, in Docker, and deploying to AWS.

---

## Option A — Docker (recommended)

The fastest way to get a fully working environment with PostgreSQL and Redis.

### Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/bythebug/task-flow.git
cd task-flow

# 2. Create your environment file
cp .env.example .env
# Open .env and set a real JWT_SECRET_KEY:
#   python -c "import secrets; print(secrets.token_hex(32))"

# 3. Start everything
docker compose up --build

# The app is now running at http://localhost:5000
```

**Stop and clean up:**
```bash
docker compose down          # stop containers
docker compose down -v       # stop + remove volumes (wipes DB)
```

---

## Option B — Local Python + Docker infrastructure

Run the Flask app directly (faster reload, easier to attach debugger) while PostgreSQL and Redis run in Docker.

### Prerequisites
- Python 3.13
- Docker (for postgres + redis only)

### Steps

```bash
# 1. Start only the infrastructure
docker compose up postgres redis -d

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env — DATABASE_URL and JWT_SECRET_KEY are required

export $(grep -v '^#' .env | xargs)   # load .env into shell

# 5. Run the development server
python run.py
# → Running on http://127.0.0.1:5000
```

---

## Running Tests

Tests use SQLite in-memory and fakeredis — no PostgreSQL or Redis needed.

```bash
source venv/bin/activate

# Run all 66 tests
pytest

# Run with coverage
pip install pytest-cov
pytest --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_auth.py -v

# Run a specific test
pytest tests/test_permissions.py::test_permission_levels -v
```

---

## PostgreSQL Setup (manual)

If you prefer not to use Docker for the database:

```bash
# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# Create database and user
psql postgres -c "CREATE USER taskflow WITH PASSWORD 'taskflow';"
psql postgres -c "CREATE DATABASE taskflow OWNER taskflow;"

# Load the schema
psql taskflow < schema.sql

# Set DATABASE_URL in .env
DATABASE_URL=postgresql://taskflow:taskflow@localhost:5432/taskflow
```

---

## Redis Setup (manual)

```bash
# macOS
brew install redis
brew services start redis

# Verify
redis-cli ping   # → PONG

# Set REDIS_URL in .env
REDIS_URL=redis://localhost:6379/0
```

---

## Deployment to AWS

### Prerequisites
- AWS CLI: `pip install awscli && aws configure`
- Docker running
- An ECR repository: `aws ecr create-repository --repository-name task-flow`
- An ECS cluster and service (Fargate recommended)

### Deploy

```bash
export AWS_REGION=us-east-1
export ECR_REPO=task-flow
export ECS_CLUSTER=task-flow-cluster
export ECS_SERVICE=task-flow-service

./deploy.sh
```

The script:
1. Runs the test suite (fails fast if any test fails)
2. Builds the Docker image tagged with the git commit SHA
3. Authenticates with ECR and pushes
4. Triggers an ECS rolling deploy and waits for stability

### Required ECS environment variables

Set these in your ECS task definition (not in the Docker image):

| Variable | Value |
|---|---|
| `DATABASE_URL` | RDS connection string |
| `REDIS_URL` | ElastiCache connection string |
| `JWT_SECRET_KEY` | Strong random secret (32+ chars) |
| `FLASK_ENV` | `production` |

### Generating a strong JWT secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Store the output in AWS Secrets Manager or Parameter Store, then inject it into the task definition. Never put it directly in the Dockerfile or source code.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | No | Redis URL (caching disabled if unset) |
| `JWT_SECRET_KEY` | Yes | Secret for signing JWT tokens |
| `TOKEN_EXPIRY_HOURS` | No | Token lifetime (default: 24) |
| `FLASK_ENV` | No | `development` or `production` |

---

## Common Issues

**`psycopg2` fails to install**
```bash
# macOS — needs libpq
brew install libpq
pip install psycopg2-binary
```

**`Address already in use` on port 5000**
```bash
lsof -i :5000        # find the PID
kill -9 <PID>
```

**Database migrations** — this project uses `Base.metadata.create_all()` which creates tables on startup. For schema changes in production, use Alembic:
```bash
pip install alembic
alembic init migrations
```
