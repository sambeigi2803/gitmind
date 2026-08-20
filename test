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

## Design Decisions & Tradeoffs

### GitHub token encryption happens in an event, not a callback

GitHub access tokens are encrypted with AES-256-GCM before being stored in
`accounts.access_token`. The Prisma adapter writes the raw token first, so
the encryption has to happen immediately afterwards.

The obvious place for that is the `signIn` **callback** — and it has a real
advantage: returning `false` from a callback denies sign-in, so a failure to
encrypt could block login entirely and guarantee a plaintext token is never
persisted. That was the original implementation.

It doesn't work. Under the JWT session strategy, the `signIn` callback runs
*before* Auth.js persists the User and Account rows, so `prisma.user.update()`
fails with `P2025 — Record to update not found`. Sign-in is denied every time.

The fix was to move the logic to the `signIn` **event**, which fires after
persistence. The tradeoff: **events cannot deny sign-in.** If encryption
throws, the token remains in plaintext rather than login being blocked.

Why that's an acceptable risk here:

- `ENCRYPTION_KEY` is validated at startup by zod (`src/lib/env.ts`), including
  a check that it is exactly 64 hex characters. A malformed key prevents the
  app from booting at all, so the realistic window for an encryption failure
  is very small.
- `getGithubAccessToken()` throws `GithubReauthRequiredError` on any token it
  cannot decrypt, so a broken token surfaces as a "Reconnect GitHub" prompt
  rather than an opaque failure.

Two improvements that would restore the original guarantee, not yet
implemented:

1. A startup self-test that encrypts and decrypts a known string and refuses
   to boot on failure — strictly better than checking during sign-in, since it
   runs before any user can authenticate.
2. A periodic audit query flagging any `access_token` that doesn't match
   base64 ciphertext shape, as defense in depth.

### JWT sessions instead of database sessions

Database sessions allow server-side revocation, which is genuinely useful.
They also mean a DB round trip on *every* authenticated request, including
in middleware.

This project uses JWT sessions and mitigates staleness with a lazy refresh:
the `jwt` callback re-reads `username` and `plan` from Postgres only when the
token is older than an hour. Most requests cost zero database queries;
plan changes propagate within an hour.

The `Session` model is retained in the Prisma schema so switching strategies
later doesn't require a migration.

### Split auth config for the Edge runtime

`middleware.ts` runs on the Edge runtime, where `@prisma/client` is
unavailable. Importing the Prisma-backed auth config there breaks the build.

The config is therefore split: `auth.config.ts` is edge-safe (providers,
callbacks, no adapter) and used by middleware; `auth.ts` extends it with the
Prisma adapter for Server Components, Route Handlers, and Server Actions.

---

## Documentation

- `backend/BACKEND.md` — backend architecture and repo-connection flow
- `frontend/AUTH_REVIEW.md` — auth implementation review and design decisions
