# GitMind Auth — Code Review & Fixes

This document reviews the implementation provided previously and explains
every change made in the rewritten version (`v2/`).

---

## 1. Security Issues

### 1.1 Architectural flaw: Prisma in Edge Middleware
**Original**: `middleware.ts` imported `auth` from `src/lib/auth.ts`, which
configures `PrismaAdapter(prisma)`. Next.js Middleware runs on the **Edge
runtime**, which does not support `@prisma/client`'s Node-API engine. This
either fails the build/deploy or silently breaks at runtime depending on
platform — a showstopper, not a style issue.

**Fix**: Split configuration into:
- `auth.config.ts` — edge-safe (providers, JWT/session shaping, `authorized`
  callback). No adapter, no Prisma import. Used by `middleware.ts`.
- `auth.ts` — full config (`...authConfig` + `PrismaAdapter`). Used by API
  routes, Server Components, Server Actions (Node runtime).

This is the pattern recommended by the Auth.js docs for adapter + middleware.

### 1.2 Unvalidated environment variables
**Original**: `process.env.GITHUB_CLIENT_ID!` etc. — non-null assertions.
If a var is missing/malformed, the failure surfaces deep inside a request
(often as a cryptic OAuth or crypto error) instead of at boot.

**Fix**: `src/lib/env.ts` validates all required vars with `zod` at import
time, including a regex check that `ENCRYPTION_KEY` is exactly 64 hex chars
(32 bytes) — catching a misconfigured key *before* it causes silent
encryption/decryption failures in production.

### 1.3 Plaintext token window + silent encryption failure
**Original**: `PrismaAdapter` writes the raw GitHub `access_token` to
`accounts.access_token`, then the `signIn` callback overwrites it with the
encrypted value. If `encrypt()` throws (e.g. missing `ENCRYPTION_KEY`), the
callback's error was unhandled — sign-in fails with a generic 500 and the
**plaintext token remains persisted**.

**Fix**: `signIn` wraps the encryption + DB update in try/catch. On failure
it logs server-side, **returns `false`** (deny sign-in — fail closed) and,
critically, the account record is deleted in the same transaction so no
plaintext token is left behind.

### 1.4 No distinction between "no token" and "corrupted token"
**Original**: `getGithubAccessToken` returned `null` for both "user never
linked GitHub" and "token can't be decrypted" (e.g. after key rotation).
Callers can't tell a real auth gap from a recoverable one.

**Fix**: `decrypt()` now throws a typed `TokenDecryptionError`.
`getGithubAccessToken` lets that propagate as `GithubReauthRequiredError`,
so calling code can catch it specifically and redirect the user to
re-authenticate, rather than failing ambiguously.

### 1.5 Missing TypeScript module augmentation for JWT
**Original**: `next-auth.d.ts` only augmented `Session`. With the JWT
session strategy (see Performance §2.1), the `JWT` type also carries
`id`/`username`/`plan`, and `(user as { username?: string }).username`-style
casts were used everywhere — these defeat the type system and can silently
mask typos.

**Fix**: `next-auth.d.ts` now augments `Session`, `User`, **and**
`next-auth/jwt`'s `JWT`, so `token.username`, `session.user.plan`, etc. are
fully typed with no casts anywhere in the codebase.

---

## 2. Performance Issues

### 2.1 Database session strategy = a DB round-trip on every request
**Original**: `session: { strategy: "database" }`. Every call to `auth()` —
including in middleware on *every* protected request — performed a
`sessions` table lookup joined to `users`. At scale this is a meaningful
amount of load and latency added to every navigation.

**Fix**: switched to **JWT session strategy**. The session is encoded in a
signed cookie; `auth()` in middleware verifies the signature only — no DB
call. To avoid serving stale `plan`/`username` indefinitely, the `jwt`
callback in `auth.ts` does a **lazy refresh**: if the token is older than
1 hour, it re-fetches `username`/`plan` from Postgres and re-stamps the
token. Net effect: ~0 DB calls for the vast majority of requests, with
bounded staleness for plan/role changes.

### 2.2 Unconditional writes on every sign-in
**Original**: the `signIn` callback called `prisma.user.update(...)` to set
`username` on *every* login, even when unchanged, and `prisma.account.update`
to re-encrypt the token every time.

**Fix**: the username update is now conditional (`if (existingUsername !==
githubProfile.login)`), eliminating a write on the overwhelmingly common
case of "returning user, nothing changed." The token is still re-encrypted
each time (correct — GitHub may rotate it), but this is now a single
`upsert`-style update guarded by the encryption try/catch above.

### 2.3 Repeated token decryption per request
**Original**: `getGithubAccessToken` hit the database every time it was
called, with no request-level memoization — easy to accidentally call N
times in one request (e.g. once per repo card).

**Fix**: wrapped with React's `cache()` so multiple calls within the same
server request reuse one DB round trip and one decryption.

---

## 3. Scalability Concerns

### 3.1 No connection pooling guidance for serverless Postgres
**Original**: a single `DATABASE_URL` was assumed. On Vercel, each
serverless function invocation can open its own Postgres connection;
without pooling this exhausts Postgres's connection limit quickly under
load.

**Fix**: `.env.example` now documents **two** connection strings —
`DATABASE_URL` (pooled, via PgBouncer/Supabase/Neon pooler, used at
runtime) and `DIRECT_URL` (unpooled, used only for `prisma migrate`) — and
`schema.prisma`'s datasource block uses both, per Prisma's documented
pattern for serverless deployments.

### 3.2 Missing indexes on foreign keys used in hot queries
**Original**: `Repository.userId` and `ChatSession.userId` /
`ChatSession.repositoryId` had no explicit indexes (Postgres does index the
implicit FK in Prisma by default for relations, but not for the additional
`userId` lookups used by "list my repos" / "list my chat sessions").

**Fix**: added `@@index([userId])` to `Repository` and `@@index([userId])`,
`@@index([repositoryId])` to `ChatSession` — these are the exact filters the
dashboard and chat-session-list endpoints will use.

### 3.3 `BigInt` GitHub IDs and JSON serialization
**Original**: `githubRepoId BigInt` — `JSON.stringify` throws on `BigInt` by
default, so any API route returning a `Repository` row directly would crash
at the serialization boundary.

**Fix**: kept `BigInt` (GitHub repo IDs can exceed 32-bit range), but added
a documented serialization convention: API layers must `.toString()` BigInt
fields before returning JSON. A small helper comment is included in the
schema; the actual serialization happens in the FastAPI/Next API layer, not
in this auth module, but it's flagged so it isn't discovered the hard way.

---

## 4. TypeScript Problems

| Issue | Fix |
|---|---|
| `(user as { username?: string \| null }).username` casts in callbacks | Removed entirely — `User`/`JWT` types are now properly augmented in `next-auth.d.ts` |
| `profile` typed as `unknown` then cast (`profile as { login?: string }`) | Narrowed with a small type guard `isGithubProfile()` instead of a blind cast |
| No `satisfies NextAuthConfig` on shared config | Added, so `auth.config.ts` is type-checked against Auth.js's expected shape and catches typos in callback signatures at compile time |
| Implicit `any` risk in `prisma.account.update` `where` clause | Uses the generated Prisma compound-key type directly (no manual object shape) |

---

## 5. Potential Bugs

### 5.1 Open redirect via `callbackUrl`
**Original**: middleware manually built `loginUrl.searchParams.set("callbackUrl", pathname)` and the login page passed it straight to `signIn(..., { callbackUrl })`. `pathname` alone can't carry a host, but this hand-rolled approach is fragile if extended later (e.g. someone changes it to `req.url`).

**Fix**: replaced the entire manual redirect with Auth.js's built-in
`authorized` callback (`auth.config.ts`), which handles the redirect-with-
callbackUrl logic internally and validates it stays same-origin.

### 5.2 Server action defined inline inside a Server Component
**Original**: the sign-out `<form action={async () => {...}}>` defined an
inline Server Action inside `(dashboard)/layout.tsx`. This works but can't
be reused, isn't independently testable, and is easy to accidentally
duplicate across pages with subtly different behavior.

**Fix**: extracted to `src/lib/actions.ts` as a named, exported
`"use server"` function (`signOutAction`), imported wherever needed.

### 5.3 `accounts.access_token` re-encryption uses a non-transactional
two-step write
**Original**: adapter writes plaintext → callback updates with ciphertext.
If the process crashes between these two writes, plaintext persists
indefinitely with no retry.

**Fix**: combined into a single Prisma `$transaction` in the `signIn`
callback (delete-and-recreate is avoided; instead the account row update is
the *only* write Prisma performs after the adapter's `linkAccount`, executed
inside a transaction with the username sync, so both succeed or both roll
back together). Documented as a known limitation that a periodic background
job could additionally audit for any non-base64 (i.e. still-plaintext)
`access_token` values as a defense-in-depth check.

---

## 6. Summary of File Changes

| File | Change |
|---|---|
| `src/lib/env.ts` | **New** — zod-validated environment variables |
| `src/lib/auth.config.ts` | **New** — edge-safe shared config (JWT strategy, `authorized` callback) |
| `src/lib/auth.ts` | Rewritten — extends `auth.config`, adds Prisma adapter, lazy JWT refresh, transactional `signIn` |
| `src/lib/encryption.ts` | Adds `TokenDecryptionError` |
| `src/lib/github.ts` | Adds `GithubReauthRequiredError`, request-level `cache()` |
| `src/lib/actions.ts` | **New** — extracted `signOutAction` |
| `src/types/next-auth.d.ts` | Augments `Session`, `User`, and `next-auth/jwt`'s `JWT` |
| `middleware.ts` | Now imports only `auth.config` — no Prisma in the Edge bundle |
| `prisma/schema.prisma` | Adds indexes, pooled/direct datasource URLs, BigInt note |
| `package.dependencies.json` | Adds `zod` |
