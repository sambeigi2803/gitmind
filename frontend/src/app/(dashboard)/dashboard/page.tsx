// src/app/(dashboard)/dashboard/page.tsx
//
// Example protected page demonstrating both `auth()` and a guarded
// call to `getGithubAccessToken`.

import { auth } from "@/lib/auth";
import { getGithubAccessToken, GithubReauthRequiredError } from "@/lib/github";

export default async function DashboardPage() {
  const session = await auth();

  let needsReauth = false;
  try {
    if (session?.user.id) {
      await getGithubAccessToken(session.user.id);
    }
  } catch (error) {
    if (error instanceof GithubReauthRequiredError) {
      needsReauth = true;
    } else {
      throw error;
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">
        Welcome back, {session?.user?.name?.split(" ")[0]}
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Plan: {session?.user?.plan} · GitHub: @{session?.user?.username}
      </p>

      {needsReauth && (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          We need you to reconnect GitHub to access your repositories.{" "}
          <a href="/login" className="underline">
            Reconnect
          </a>
        </p>
      )}

      {/* Connected repositories list would go here */}
    </div>
  );
}
