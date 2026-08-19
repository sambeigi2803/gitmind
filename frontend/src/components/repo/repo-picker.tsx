// src/components/repo/repo-picker.tsx
//
// Client component listing the user's GitHub repos with a connect
// action. Uses useTransition so the pending state is driven by React
// rather than hand-managed loading booleans.

"use client";

import { useState, useTransition } from "react";
import { connectRepositoryAction } from "@/lib/actions/repos";
import type { GithubRepoSummary } from "@/lib/api/repos";

export function RepoPicker({ repos }: { repos: GithubRepoSummary[] }) {
  const [isPending, startTransition] = useTransition();
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const filtered = repos.filter((r) =>
    r.full_name.toLowerCase().includes(query.toLowerCase())
  );

  function handleConnect(repo: GithubRepoSummary) {
    setError(null);
    setConnectingId(repo.github_repo_id);

    startTransition(async () => {
      const result = await connectRepositoryAction(
        repo.github_repo_id,
        repo.full_name
      );
      // On success the action redirects, so we only get here on failure.
      if (result && !result.ok) {
        setError(result.error);
        setConnectingId(null);
      }
    });
  }

  return (
    <div className="space-y-4">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter repositories…"
        className="w-full rounded-md border px-3 py-2 text-sm"
        aria-label="Filter repositories"
      />

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No repositories match “{query}”.
        </p>
      ) : (
        <ul className="divide-y rounded-md border">
          {filtered.map((repo) => (
            <li
              key={repo.github_repo_id}
              className="flex items-center justify-between gap-4 p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{repo.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {repo.private ? "Private" : "Public"}
                  {repo.language && ` · ${repo.language}`}
                  {repo.description && ` · ${repo.description}`}
                </p>
              </div>

              <button
                onClick={() => handleConnect(repo)}
                disabled={repo.already_connected || isPending}
                className="shrink-0 rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                {repo.already_connected
                  ? "Connected"
                  : connectingId === repo.github_repo_id
                    ? "Connecting…"
                    : "Connect"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
