// src/app/(dashboard)/layout.tsx
//
// Shared layout for all authenticated app routes. Middleware already
// blocks unauthenticated requests via the `authorized` callback, but
// this server-side check remains as defense-in-depth (cheap under the
// JWT strategy - cookie verification only, no DB hit) and provides
// `session` for rendering the user's avatar/name.

import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { signOutAction } from "@/lib/actions/auth";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-64 border-r p-4">
        <div className="flex items-center gap-3">
          {session.user.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={session.user.image}
              alt={session.user.name ?? "User avatar"}
              className="h-8 w-8 rounded-full"
            />
          )}
          <div>
            <p className="text-sm font-medium">{session.user.name}</p>
            <p className="text-xs text-muted-foreground">
              @{session.user.username}
            </p>
          </div>
        </div>

        <nav className="mt-6 space-y-1 text-sm">
          <a href="/dashboard" className="block rounded-md px-2 py-1.5 hover:bg-gray-100">
            Dashboard
          </a>
          <a href="/settings" className="block rounded-md px-2 py-1.5 hover:bg-gray-100">
            Settings
          </a>
        </nav>

        <form action={signOutAction} className="mt-6">
          <button
            type="submit"
            className="w-full rounded-md border px-2 py-1.5 text-sm hover:bg-gray-50"
          >
            Sign out
          </button>
        </form>
      </aside>

      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
