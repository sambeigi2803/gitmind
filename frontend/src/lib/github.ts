// src/lib/github.ts
//
// Retrieves a decrypted GitHub access token for the current user,
// for server-side calls to the GitHub API (listing repos, ingestion, etc.)

import { cache } from "react";
import { prisma } from "@/lib/prisma";
import { decrypt, TokenDecryptionError } from "@/lib/encryption";

/**
 * Thrown when a user has no usable GitHub token and must re-authenticate -
 * either they never linked GitHub, or the stored token can't be decrypted
 * (e.g. ENCRYPTION_KEY was rotated). Distinct from "GitHub API returned an
 * error" - this means GitMind itself can't even attempt the call.
 */
export class GithubReauthRequiredError extends Error {
  constructor(message = "GitHub re-authentication required") {
    super(message);
    this.name = "GithubReauthRequiredError";
  }
}

/**
 * Returns the decrypted GitHub access token for a given user.
 *
 * Memoized per-request with React's `cache()` - if multiple components
 * or service calls need the token within the same render/request, only
 * one DB query and one decryption is performed.
 *
 * @throws {GithubReauthRequiredError} if no token exists or it can't be decrypted.
 */
export const getGithubAccessToken = cache(async (userId: string): Promise<string> => {
  const account = await prisma.account.findFirst({
    where: { userId, provider: "github" },
    select: { access_token: true },
  });

  if (!account?.access_token) {
    throw new GithubReauthRequiredError("No GitHub account linked");
  }

  try {
    return decrypt(account.access_token);
  } catch (error) {
    if (error instanceof TokenDecryptionError) {
      throw new GithubReauthRequiredError("Stored GitHub token could not be decrypted");
    }
    throw error;
  }
});
