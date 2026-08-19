// src/lib/actions/repos.ts
//
// Server Actions for repository management.
//
// Using Server Actions rather than client-side fetches keeps the JWT
// minting (and therefore AUTH_SECRET) entirely server-side, and lets us
// call revalidatePath so the dashboard reflects changes immediately.

"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import {
  connectRepository,
  disconnectRepository,
  reindexRepository,
} from "@/lib/api/repos";

export type ActionResult =
  | { ok: true }
  | { ok: false; error: string; needsReauth?: boolean };

function toResult(error: unknown): ActionResult {
  if (error instanceof ApiError) {
    return {
      ok: false,
      error: error.message,
      needsReauth: error.needsGithubReauth,
    };
  }
  return { ok: false, error: "Something went wrong. Please try again." };
}

export async function connectRepositoryAction(
  githubRepoId: string,
  fullName: string
): Promise<ActionResult> {
  let repoId: string;

  try {
    const result = await connectRepository({
      github_repo_id: githubRepoId,
      full_name: fullName,
    });
    repoId = result.repository.id;
  } catch (error) {
    return toResult(error);
  }

  // redirect() throws internally, so it must sit outside the try block -
  // otherwise the catch would swallow it and the navigation never happens.
  revalidatePath("/dashboard");
  redirect(`/repos/${repoId}`);
}

export async function reindexRepositoryAction(
  repoId: string
): Promise<ActionResult> {
  try {
    await reindexRepository(repoId);
    revalidatePath(`/repos/${repoId}`);
    return { ok: true };
  } catch (error) {
    return toResult(error);
  }
}

export async function disconnectRepositoryAction(
  repoId: string
): Promise<ActionResult> {
  try {
    await disconnectRepository(repoId);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (error) {
    return toResult(error);
  }
}
