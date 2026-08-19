// middleware.ts (project root, alongside next.config.js)
//
// Edge runtime. Imports ONLY auth.config.ts (no Prisma anywhere in
// this bundle's dependency graph). The `authorized` callback in
// auth.config.ts decides access; Auth.js handles the redirect to
// /login with a validated callbackUrl automatically.

import NextAuth from "next-auth";
import authConfig from "@/lib/auth.config";

export default NextAuth(authConfig).auth;

// Only run on routes that require authentication. Marketing pages,
// /login, and /api/auth/* are intentionally excluded.
export const config = {
  matcher: ["/dashboard/:path*", "/repos/:path*", "/settings/:path*"],
};
