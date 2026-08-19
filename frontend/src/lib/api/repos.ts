// src/lib/api/repos.ts
//
// Typed API functions for repository endpoints. These mirror the
// Pydantic schemas in app/schemas/repository.py - consider generating
// them from the backend's OpenAPI spec (openapi-typescript) once the
// API stabilizes, to eliminate drift.

import { apiFetch } from "@/lib/api/client";

export type IndexingStatus = "pending" | "processing" | "done" | "failed";

export interface GithubRepoSummary {
  /** Serialized as a string by the backend - GitHub IDs exceed 2^53. */
  github_repo_id: string;
  full_name: string;
  description: string | null;
  private: boolean;
  default_branch: string;
  language: string | null;
  stargazers_count: number;
  size_kb: number;
  updated_at: string | null;
  already_connected: boolean;
}

export interface Repository {
  id: string;
  full_name: string;
  default_branch: string | null;
  visibility: string | null;
  indexing_status: IndexingStatus;
  last_indexed_at: string | null;
  created_at: string;
}

export interface Job {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export function listAvailableRepositories(page = 1) {
  return apiFetch<GithubRepoSummary[]>(`/api/v1/repos/available?page=${page}`);
}

export function listConnectedRepositories() {
  return apiFetch<Repository[]>("/api/v1/repos");
}

export function connectRepository(input: {
  github_repo_id: string;
  full_name: string;
}) {
  return apiFetch<{ repository: Repository; job: Job }>(
    "/api/v1/repos/connect",
    {
      method: "POST",
      body: JSON.stringify({
        // Backend expects an integer; safe to send as a number here
        // because it's parsed server-side into a 64-bit Python int.
        github_repo_id: Number(input.github_repo_id),
        full_name: input.full_name,
      }),
    }
  );
}

export function getRepository(repoId: string) {
  return apiFetch<Repository>(`/api/v1/repos/${repoId}`);
}

export function reindexRepository(repoId: string) {
  return apiFetch<Job>(`/api/v1/repos/${repoId}/reindex`, { method: "POST" });
}

export function disconnectRepository(repoId: string) {
  return apiFetch<void>(`/api/v1/repos/${repoId}`, { method: "DELETE" });
}

export function getJob(jobId: string) {
  return apiFetch<Job>(`/api/v1/jobs/${jobId}`);
}
