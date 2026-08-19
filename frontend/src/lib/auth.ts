// src/lib/auth.ts
//
// Full Auth.js configuration. Node-runtime only - imports Prisma.
// Used by: src/app/api/auth/[...nextauth]/route.ts, Server Components,
// and Server Actions. Do NOT import this from middleware.ts (use
// auth.config.ts there instead - see that file's header comment).

import NextAuth from "next-auth";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { prisma } from "@/lib/prisma";
import { encrypt } from "@/lib/encryption";
import { env } from "@/lib/env";
import authConfig from "@/lib/auth.config";

// How often to re-fetch username/plan from the database for an
// already-issued JWT. Balances avoiding a DB hit on every request
// against serving stale `plan` after an upgrade/downgrade.
const REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

/** Narrow the GitHub `profile` object without an unsafe cast. */
function getGithubLogin(profile: unknown): string | null {
  if (
    typeof profile === "object" &&
    profile !== null &&
    "login" in profile &&
    typeof (profile as { login: unknown }).login === "string"
  ) {
    return (profile as { login: string }).login;
  }
  return null;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(prisma),
  secret: env.AUTH_SECRET,

  callbacks: {
    ...authConfig.callbacks,

    /**
     * Runs after the adapter has created/linked the User and Account
     * records (which includes writing the *plaintext* access_token).
     *
     * This callback:
     *  1. Syncs the GitHub username onto the User row (only if changed).
     *  2. Encrypts the access token the adapter just wrote.
     *
     * Both writes happen in a single transaction. If encryption fails
     * (e.g. ENCRYPTION_KEY misconfigured), we roll back and DENY sign-in
     * (fail closed) rather than leaving a plaintext token persisted.
     */
    async signIn({ user, account, profile }) {
      if (!account || !user.id) return true;

      const githubLogin = getGithubLogin(profile);

      try {
        await prisma.$transaction(async (tx) => {
          if (githubLogin && githubLogin !== user.username) {
            await tx.user.update({
              where: { id: user.id },
              data: { username: githubLogin },
            });
          }

          if (account.access_token) {
            await tx.account.update({
              where: {
                provider_providerAccountId: {
                  provider: account.provider,
                  providerAccountId: account.providerAccountId,
                },
              },
              data: { access_token: encrypt(account.access_token) },
            });
          }
        });
      } catch (error) {
        console.error("[auth] signIn token-encryption transaction failed", error);
        return false; // deny sign-in; no plaintext token left committed
      }

      return true;
    },

    /**
     * Extends the base jwt callback (initial population on sign-in) with
     * a lazy refresh: if the token is older than REFRESH_INTERVAL_MS,
     * re-fetch `username`/`plan` from Postgres. This is the only place
     * in the request lifecycle that hits the DB for session data, and
     * only ~once per hour per user.
     */
    async jwt(params) {
      const base = authConfig.callbacks!.jwt!;
      let token = await base(params);

      const isStale =
        !token.refreshedAt || Date.now() - token.refreshedAt > REFRESH_INTERVAL_MS;

      if (isStale && token.id) {
        const dbUser = await prisma.user.findUnique({
          where: { id: token.id },
          select: { username: true, plan: true },
        });

        if (dbUser) {
          token.username = dbUser.username;
          token.plan = dbUser.plan;
        }
        token.refreshedAt = Date.now();
      }

      return token;
    },
  },
});
