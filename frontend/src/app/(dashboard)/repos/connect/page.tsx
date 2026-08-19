// src/app/(dashboard)/repos/connect/page.tsx
//
// Server Component that fetches the user's GitHub repos and hands them
// to the client-side picker. Fetching on the server means the JWT never
// reaches the browser and the list is available on first paint.

import { ApiError } from "@/lib/api/client";
import { listAvailableRepositories } from "@/lib/api/repos";
import { RepoPicker } from "@/components/repo/repo-picker";

export default async function ConnectRepoPage() {
  try {
    const repos = await listAvailableRepositories();

    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="text-xl font-semibold">Connect a repository</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose a repository to index. Indexing runs in the background and
            usually takes a few minutes.
          </p>
        </div>

        <RepoPicker repos={repos} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError && error.needsGithubReauth) {
      return (
        <div className="mx-auto max-w-md py-12 text-center">
          <h1 className="text-lg font-semibold">Reconnect GitHub</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            We couldn&apos;t access your GitHub account. Sign in again to
            refresh your connection.
          </p>
          <a
            href="/login"
            className="mt-4 inline-block rounded-md bg-black px-4 py-2 text-sm text-white"
          >
            Reconnect GitHub
          </a>
        </div>
      );
    }
    throw error; // let the route's error boundary handle anything else
  }
}
