// src/lib/api/client.ts
//
// Shared fetch wrapper for the FastAPI backend.
//
// Attaches the caller's JWT, normalizes the backend's error envelope
// ({ error: { code, message } }) into a typed ApiError, and centralizes
// the base URL so no component ever hardcodes an endpoint.

import { auth } from "@/lib/auth";
import { SignJWT } from "jose";
import { env } from "@/lib/env";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the user must reconnect GitHub before this can succeed. */
  get needsGithubReauth(): boolean {
    return this.code === "github_reauth_required";
  }
}

/**
 * Mints a plain HS256-signed JWT for the backend.
 *
 * NOTE: Auth.js's own `encode()` produces a JWE (encrypted), which
 * python-jose cannot verify. The backend expects a standard signed JWT,
 * so we sign one directly with the shared AUTH_SECRET.
 */
async function getAuthToken(): Promise<string> {
  const session = await auth();
  if (!session?.user?.id) {
    throw new ApiError(401, "unauthenticated", "Not signed in");
  }

  const secret = new TextEncoder().encode(env.AUTH_SECRET);

  return new SignJWT({
    id: session.user.id,
    username: session.user.username,
    plan: session.user.plan,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(session.user.id)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(secret);
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();

  const response = await fetch(`${env.BACKEND_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
    cache: "no-store",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.error?.code ?? "unknown_error",
      body?.error?.message ?? `Request failed with status ${response.status}`
    );
  }

  return body as T;
}
