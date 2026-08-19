// src/app/api/auth/[...nextauth]/route.ts
//
// Catch-all route handling all Auth.js endpoints:
// /api/auth/signin, /api/auth/callback/github,
// /api/auth/signout, /api/auth/session, etc.
//
// Imports the FULL config (with Prisma adapter) - this route runs on
// the Node.js runtime by default, so Prisma is safe here.

import { handlers } from "@/lib/auth";

export const { GET, POST } = handlers;
