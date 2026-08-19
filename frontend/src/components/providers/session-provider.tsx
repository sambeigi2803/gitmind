// src/components/providers/session-provider.tsx
//
// Auth.js's `useSession()` hook (for client components) requires a
// <SessionProvider> in the tree. This thin wrapper keeps the root
// layout a Server Component while still providing context to client
// components further down.

"use client";

import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";

export function AuthProvider({
  children,
  session,
}: {
  children: React.ReactNode;
  session: Session | null;
}) {
  return <SessionProvider session={session}>{children}</SessionProvider>;
}
