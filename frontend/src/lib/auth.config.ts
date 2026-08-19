// src/lib/auth.config.ts
//
// Edge-safe Auth.js configuration: NO Prisma adapter and NO Prisma
// import anywhere in this file or its dependencies. This is the
// config used by middleware.ts, which runs on the Edge runtime where
// @prisma/client's Node engine is unavailable.
//
// `auth.ts` extends this config with the Prisma adapter for use in
// Server Components, Route Handlers, and Server Actions (Node runtime).

import type { NextAuthConfig } from "next-auth";
import GitHub from "next-auth/providers/github";
import { env } from "@/lib/env";

export default {
  providers: [
    GitHub({
      clientId: env.GITHUB_CLIENT_ID,
      clientSecret: env.GITHUB_CLIENT_SECRET,
      // `repo` grants access to private repos. Use "public_repo" if the
      // MVP only supports public repositories.
      authorization: {
        params: { scope: "read:user user:email repo" },
      },
    }),
  ],

  // JWT strategy: session is a signed cookie, verifiable without a DB
  // round trip. See REVIEW.md ("Performance Issues") for the tradeoffs
  // and the lazy-refresh pattern used in auth.ts to keep plan/username
  // reasonably fresh.
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  callbacks: {
    /**
     * Populates the token on initial sign-in. `user`/`account` are only
     * defined on the first call after a successful sign-in; on subsequent
     * calls only `token` is passed, so we must not assume `user` exists.
     *
     * auth.ts wraps this callback to additionally perform a lazy DB
     * refresh of `username`/`plan` when the token is stale.
     */
    jwt({ token, user }) {
      if (user) {
        token.id = user.id!;
        token.username = user.username ?? null;
        token.plan = user.plan ?? "free";
        token.refreshedAt = Date.now();
      }
      return token;
    },

    session({ session, token }) {
      session.user.id = token.id;
      session.user.username = token.username;
      session.user.plan = token.plan;
      return session;
    },

    /**
     * Used by middleware (via `NextAuth(authConfig).auth`) to decide
     * whether a request may proceed. Returning `false` triggers Auth.js's
     * built-in redirect to `pages.signIn` with a same-origin-validated
     * `callbackUrl` - no manual redirect/open-redirect handling needed.
     */
    authorized({ auth }) {
      return !!auth?.user;
    },
  },
} satisfies NextAuthConfig;
