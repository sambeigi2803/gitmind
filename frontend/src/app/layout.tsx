// src/app/layout.tsx
//
// Root layout. Fetches the session once on the server (cheap - no DB
// hit under the JWT strategy, just cookie verification) and passes it
// into AuthProvider to avoid an extra client-side fetch on first load.

import type { Metadata } from "next";
import { auth } from "@/lib/auth";
import { AuthProvider } from "@/components/providers/session-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "GitMind",
  description: "AI-powered codebase explorer",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  return (
    <html lang="en">
      <body>
        <AuthProvider session={session}>{children}</AuthProvider>
      </body>
    </html>
  );
}
