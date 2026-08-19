// src/lib/prisma.ts
//
// Prisma Client singleton. Prevents exhausting database connections
// during Next.js hot-reloads in development.
//
// IMPORTANT (serverless): DATABASE_URL should point at a *pooled*
// connection (PgBouncer / Supabase pooler / Neon pooler). A separate
// DIRECT_URL (unpooled) is used only by `prisma migrate` - see
// prisma/schema.prisma and .env.example.

import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
