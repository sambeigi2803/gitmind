// src/lib/actions/auth.ts
//
// Server Actions ("use server"). Extracted from layouts/pages so they
// are reusable and independently testable, rather than defined inline
// inside Server Components.

"use server";

import { signOut } from "@/lib/auth";

export async function signOutAction() {
  await signOut({ redirectTo: "/" });
}
