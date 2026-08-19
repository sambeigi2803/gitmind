<<<<<<< HEAD
# gitmind
=======
# GitMind

AI-powered codebase explorer. Connect a GitHub repository, chat with your
code, generate documentation, and explore architecture.

**Stack**: Next.js 14 · TypeScript · FastAPI · Celery · PostgreSQL/pgvector · Redis

---

## Repository Layout

```
gitmind/
├── frontend/       Next.js 14 app (App Router) — auth, UI, API client
├── backend/        FastAPI app — REST API, services, Celery workers
└── .vscode/        Shared editor settings
```

Both apps talk to **the same PostgreSQL database** but own different tables:

| Tables | Owner | Migrated by |
|---|---|---|
| `users`, `accounts`, `sessions`, `repositories`, `chat_sessions` | frontend | Prisma |
| `repo_files`, `code_chunks`, `jobs` | backend | Alembic |

---

## Prerequisites

- Node.js 20+
- Python 3.12+
- Docker (for Postgres + Redis)

---

## Setup

### 1. Generate shared secrets

Both apps must use **identical** values for these two variables. A mismatch
fails at request time, not startup, so get this right first:

```bash
openssl rand -base64 32   # → AUTH_SECRET
openssl rand -hex 32      # → ENCRYPTION_KEY
```

`AUTH_SECRET` signs the JWT the frontend issues and the backend verifies.
`ENCRYPTION_KEY` encrypts GitHub tokens the frontend writes and the backend
decrypts.

### 2. Create a GitHub OAuth App

At https://github.com/settings/developers:

- Homepage URL: `http://localhost:3000`
- Authorization callback URL: `http://localhost:3000/api/auth/callback/github`

### 3. Start infrastructure

```bash
cd backend
docker compose up postgres redis -d
```

### 4. Backend

```bash
cd backend
cp .env.example .env          # paste in the secrets from step 1
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Frontend

```bash
cd frontend
cp .env.example .env.local    # same AUTH_SECRET + ENCRYPTION_KEY
npm install
npx prisma migrate dev --name init
```

Run Prisma's migration **before** Alembic — the backend's tables have
foreign keys into `users` and `repositories`.

```bash
cd ../backend && alembic upgrade head
```

### 6. Run

Three terminals:

```bash
cd frontend && npm run dev                                              # :3000
cd backend  && uvicorn app.main:app --reload --port 8000                # :8000
cd backend  && celery -A app.workers.celery_app worker --loglevel=info
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs

---

## Verifying the Setup

1. Visit http://localhost:3000/dashboard → redirects to `/login`
2. Sign in with GitHub → lands on the dashboard
3. Check the database — the stored token should be ciphertext, not a
   GitHub token:
   ```sql
   SELECT provider, access_token FROM accounts;
   ```
4. Visit `/repos/connect` → your GitHub repos should list
5. Click **Connect** → a `jobs` row appears and the worker log shows the
   ingestion task running

If step 4 shows a "Reconnect GitHub" screen, `ENCRYPTION_KEY` differs
between the two `.env` files.

---

## Current Status

**Working:**
- GitHub OAuth, JWT sessions, protected routes, encrypted token storage
- Repository connect / list / reindex / disconnect
- Job queue with status tracking, retries, and progress reporting

**Stubbed** (`TODO(phase-2)` in `backend/app/workers/tasks/ingest.py`):
- Repo download, file filtering, AST chunking, embedding, repo summary

**Not started:**
- Chat/RAG endpoint, documentation generation, architecture graph

---

## Documentation

- `backend/BACKEND.md` — backend architecture and repo-connection flow
- `frontend/AUTH_REVIEW.md` — auth implementation review and design decisions
>>>>>>> 31e2098 (Initial project scaffold: Next.js frontend + FastAPI backend)
