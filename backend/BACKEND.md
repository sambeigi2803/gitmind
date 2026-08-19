# GitMind — Backend & Repository Connection Flow

**Stack**: FastAPI · SQLAlchemy 2.0 (async) · Celery · Redis · PostgreSQL/pgvector

---

## 1. Backend Folder Structure

```
gitmind-backend/
├── app/
│   ├── main.py                      # FastAPI entrypoint, exception handlers, CORS
│   ├── core/
│   │   ├── config.py                # pydantic-settings, validated at startup
│   │   ├── security.py              # JWT verification + AES-GCM token decryption
│   │   └── exceptions.py            # Domain exceptions (HTTP-agnostic)
│   ├── db/
│   │   └── session.py               # Async engine, session factory, get_db dependency
│   ├── models/
│   │   └── repository.py            # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── repository.py            # Pydantic request/response contracts
│   ├── services/
│   │   ├── github_service.py        # GitHub REST client
│   │   └── repository_service.py    # Business logic + authorization
│   ├── api/v1/
│   │   ├── router.py                # Aggregates v1 routers
│   │   └── routes/
│   │       ├── repositories.py      # /api/v1/repos/*
│   │       └── jobs.py              # /api/v1/jobs/*, /api/v1/repos/{id}/jobs
│   └── workers/
│       ├── celery_app.py            # Celery config
│       └── tasks/ingest.py          # Ingestion task
├── alembic/                         # Migrations for backend-owned tables
├── tests/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

### Why this layering

**Routes → Services → Models.** Routes only parse input and shape output. All
business logic and *all authorization* lives in services. This matters
specifically because Celery workers also call these services — if
authorization lived in the route layer, the worker path would bypass it
entirely.

**Domain exceptions instead of `HTTPException`.** `app/core/exceptions.py`
defines errors like `NotFoundError` and `PlanLimitExceededError` that carry
their own status code and error code. A single handler in `main.py` maps
them to HTTP responses. Services stay importable from Celery, where
`HTTPException` would be meaningless.

**Schemas separate from models.** ORM models contain columns the API must
never return (encrypted tokens, internal user IDs). Keeping Pydantic
schemas separate makes leaking them impossible by accident rather than
merely unlikely.

---

## 2. Database Ownership Split

The frontend and backend share one Postgres database but own different
tables:

| Tables | Owner | Migrated by |
|---|---|---|
| `users`, `accounts`, `sessions`, `verification_tokens` | Frontend | Prisma |
| `repositories`, `chat_sessions` | Frontend | Prisma |
| `repo_files`, `code_chunks`, `jobs` | Backend | Alembic |

The backend's SQLAlchemy models for `users` and `accounts` are **read-only
mirrors** — the backend queries them but never migrates them. This avoids
two migration tools fighting over the same tables, which is a genuinely
painful failure mode.

---

## 3. Authentication Between Frontend and Backend

There is **one** identity system. Auth.js issues a JWT signed with
`AUTH_SECRET`; the backend verifies that same token using the same secret.

```
Browser → Next.js Server Action → (mints JWT) → FastAPI
                                                   ↓
                                            verify signature
                                            extract id/username/plan
```

`src/lib/api/client.ts` mints the token server-side in a Server Action, so
`AUTH_SECRET` never reaches the browser. `app/core/security.py` verifies it
and returns a `CurrentUser`, injected into every protected route via
FastAPI's dependency system.

The backend also needs to *decrypt* GitHub tokens the frontend encrypted.
`decrypt_token()` in `security.py` mirrors `src/lib/encryption.ts` exactly —
same AES-256-GCM, same `[iv][authTag][ciphertext]` layout. One subtlety:
Node's `crypto` keeps the auth tag separate, while Python's `AESGCM`
expects it appended to the ciphertext, so the Python side reorders the
bytes before decrypting.

**Both services must share identical `AUTH_SECRET` and `ENCRYPTION_KEY`
values.** This is the single most likely deployment misconfiguration; both
are validated at startup on each side.

---

## 4. Repository Connection Flow

### End to end

1. User visits `/repos/connect`. The Server Component calls
   `listAvailableRepositories()`.
2. Backend fetches the user's encrypted GitHub token from `accounts`,
   decrypts it, and calls `GET /user/repos`. It cross-references already-
   connected repo IDs so the UI can disable them.
3. User clicks **Connect** → `connectRepositoryAction` Server Action →
   `POST /api/v1/repos/connect`.
4. `repository_service.connect_repository` runs its checks **in cost order**,
   cheapest first:
   - plan limit (one `COUNT` query)
   - duplicate check (one indexed lookup)
   - **GitHub verification** — fetch the repo with *this user's* token
   - ID/name consistency check
   - repo size vs `MAX_REPO_SIZE_MB`
5. On success: `Repository` + `Job` rows are created in one transaction.
6. **After commit**, the Celery task is enqueued.
7. Backend returns `202 Accepted` with both records. The action redirects to
   the repo page, which polls the job for progress.

### Two ordering decisions worth calling out

**GitHub verification before insert.** Without step 4's verification, a user
could POST an arbitrary `github_repo_id` and connect a repository they
can't actually access. Verifying with *their* token means GitHub itself
enforces the permission check. The ID/name match then prevents pairing a
valid ID with someone else's `full_name`.

**Enqueue after commit, not inside the transaction.** Celery brokers aren't
transactional. If the task were enqueued inside the transaction, a worker
could pick it up and query for a `Repository` row the transaction hasn't
committed yet — a race that appears only under load and is miserable to
debug.

**404 instead of 403 for other users' repos.** `get_owned_repository` returns
`NotFoundError` when a repo exists but belongs to someone else, so the API
doesn't leak which repository IDs are real.

---

## 5. Background Job Design

### Sync sessions in workers

Celery tasks are synchronous. `app/workers/tasks/ingest.py` uses a separate
**sync** SQLAlchemy engine rather than reusing the async one from
`db/session.py`. Mixing an async engine into a sync worker causes event-loop
errors that surface unpredictably under concurrency.

### Retry semantics

```python
max_retries=3, retry_backoff=60, retry_backoff_max=600, retry_jitter=True
```

The expected failure mode is transient — GitHub rate limits, embedding API
429s. Exponential backoff with jitter prevents a thundering herd of retries
after a rate-limit window. After exhausting retries the repo is marked
`failed` and the error is recorded on the job for display in the UI.

During retries the repo stays in `processing` rather than flickering to
`failed`, so the UI doesn't show a scary state for work that's still in
flight.

### Celery configuration choices

- `worker_prefetch_multiplier=1` — ingestion runtimes vary enormously
  (a 50-file repo vs a 5,000-file one). Prefetching would let one worker
  hoard queued tasks while another sits idle.
- `task_acks_late=True` + `task_reject_on_worker_lost=True` — if a worker
  dies mid-task, the task is redelivered rather than silently lost.
- `task_time_limit=30min` — a hard ceiling so a pathological repo can't
  occupy a worker indefinitely.

### Idempotency

The task is written to be safely re-runnable. Re-running replaces derived
data rather than duplicating it. It also handles the case where the repo
was disconnected between enqueue and execution — that returns `skipped`,
not an error, since nothing is actually wrong.

The `repo_files.sha` column stores each file's Git blob SHA. On re-index,
unchanged files are skipped entirely — the single biggest cost saving in
the pipeline, since embedding is the expensive step.

---

## 6. What's Stubbed vs. Complete

**Complete and production-ready:**
- API surface, request/response schemas, error envelope
- JWT verification and cross-service token decryption
- Authorization and ownership checks
- Connect / list / reindex / disconnect flows
- Job lifecycle, status tracking, retry and failure handling
- Frontend API client, Server Actions, repo picker UI
- Docker Compose dev environment

**Stubbed with `TODO(phase-2)` markers** inside `ingest.py` — the five
pipeline steps (fetch tarball, filter files, AST chunking, embed + persist,
repo summary). The scaffolding around them — status transitions, progress
reporting, error handling, idempotency — is complete, so filling these in
doesn't require reshaping anything.

---

## 7. Running Locally

```bash
# 1. Start Postgres (with pgvector) and Redis
docker compose up postgres redis -d

# 2. Configure - AUTH_SECRET and ENCRYPTION_KEY must match the frontend
cp .env.example .env

# 3. Run the frontend's Prisma migrations first (creates users/accounts),
#    then the backend's Alembic migrations
cd ../gitmind-frontend && npx prisma migrate dev
cd ../gitmind-backend && alembic upgrade head

# 4. Start the API and a worker
docker compose up api worker

# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health
```

---

## 8. Suggested Next Steps

1. **Implement the ingestion pipeline internals** — the five stubbed steps.
   This is the highest-value remaining work and the most technically
   interesting part of the portfolio.
2. **Add the `code_chunks` model and Alembic migration** with the pgvector
   HNSW index from the technical specification.
3. **Build the chat/RAG endpoint** with SSE streaming.
4. **Add tests** — the service layer is deliberately structured to be
   testable without HTTP, so `repository_service` is a natural starting
   point for demonstrating testing discipline.
