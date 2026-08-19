// src/lib/env.ts
//
// Validates required environment variables at import time using zod.
// Importing this module anywhere (including auth.config.ts, which is
// bundled for the Edge runtime) will throw immediately with a clear,
// human-readable error if configuration is missing or malformed -
// instead of failing later with a cryptic crypto/OAuth error mid-request.

import { z } from "zod";

const envSchema = z.object({
  // Pooled connection string (PgBouncer/Supabase/Neon pooler) - used at runtime.
  DATABASE_URL: z.string().url(),

  // Auth.js signing secret. Generate with: openssl rand -base64 32
  AUTH_SECRET: z.string().min(32, "AUTH_SECRET must be at least 32 characters"),

  // Used by Auth.js to build absolute callback/redirect URLs in production.
  AUTH_URL: z.string().url().optional(),

  GITHUB_CLIENT_ID: z.string().min(1, "GITHUB_CLIENT_ID is required"),
  GITHUB_CLIENT_SECRET: z.string().min(1, "GITHUB_CLIENT_SECRET is required"),

  // 32-byte key, hex-encoded (64 chars). Generate with: openssl rand -hex 32
  // MUST match the FastAPI backend's ENCRYPTION_KEY - the backend decrypts
  // GitHub tokens that this app encrypted.
  ENCRYPTION_KEY: z
    .string()
    .regex(/^[0-9a-fA-F]{64}$/, "ENCRYPTION_KEY must be exactly 64 hex characters (32 bytes)"),

  // Base URL of the FastAPI backend (no trailing slash).
  BACKEND_API_URL: z.string().url().default("http://localhost:8000"),
});

function loadEnv() {
  const parsed = envSchema.safeParse(process.env);

  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(
      `Invalid environment configuration:\n${issues}\n\nCheck .env.local against .env.example.`
    );
  }

  return parsed.data;
}

export const env = loadEnv();
