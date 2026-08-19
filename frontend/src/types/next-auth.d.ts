// src/types/next-auth.d.ts
//
// Extends Auth.js's built-in types with GitMind-specific fields.
// This removes the need for any `as { ... }` casts in callbacks -
// `token.username`, `session.user.plan`, etc. are fully typed.

import { DefaultSession, DefaultUser } from "next-auth";
import { JWT as DefaultJWT } from "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      username: string | null;
      plan: string;
    } & DefaultSession["user"];
  }

  // The shape returned by the Prisma adapter (createUser/getUser/etc.)
  interface User extends DefaultUser {
    username?: string | null;
    plan?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    id: string;
    username: string | null;
    plan: string;
    /** Unix ms timestamp of the last DB-backed refresh of plan/username. */
    refreshedAt?: number;
  }
}
