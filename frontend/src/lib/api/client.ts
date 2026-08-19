// src/lib/api/client.ts
//
// Shared fetch wrapper for the FastAPI backend.
//
// Attaches the caller's JWT, normalizes the backend's error envelope
// ({ error: { code, message } }) into a typed ApiError, and centralizes
// the base URL so no component ever hardcodes an endpoint.

import { auth } from "@/lib/auth";
import { encode } from "next-auth/jwt";
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
 * Builds the bearer token sent to the backend. The backend verifies it
 * with the same AUTH_SECRET, so identity stays single-sourced in Auth.js.
 */
async function getAuthToken(): Promise<string> {
  const session = await auth();
  if (!session?.user?.id) {
    throw new ApiError(401, "unauthenticated", "Not signed in");
  }

  return encode({
    token: {
      id: session.user.id,
      username: session.user.username,
      plan: session.user.plan,
    },
    secret: env.AUTH_SECRET,
    salt: "",
  });
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
