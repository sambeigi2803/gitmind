// src/lib/encryption.ts
//
// Encrypts/decrypts sensitive strings (GitHub access tokens) before
// they are persisted, using AES-256-GCM with a per-encryption random IV.
//
// ENCRYPTION_KEY is validated by src/lib/env.ts (64 hex chars / 32 bytes).

import crypto from "crypto";
import { env } from "@/lib/env";

const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 12; // recommended for GCM
const AUTH_TAG_LENGTH = 16;

/**
 * Thrown by `decrypt` when a ciphertext can't be authenticated/decoded -
 * e.g. ENCRYPTION_KEY was rotated, or the value isn't ciphertext at all.
 * Callers should treat this as "the underlying secret is unusable" and
 * prompt re-authentication rather than surfacing a generic error.
 */
export class TokenDecryptionError extends Error {
  constructor(message = "Failed to decrypt token") {
    super(message);
    this.name = "TokenDecryptionError";
  }
}

function getKey(): Buffer {
  return Buffer.from(env.ENCRYPTION_KEY, "hex");
}

/**
 * Encrypts a plaintext string. Returns a base64 string containing
 * [iv][authTag][ciphertext], safe to store in a TEXT column.
 */
export function encrypt(plaintext: string): string {
  const key = getKey();
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  const encrypted = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const authTag = cipher.getAuthTag();

  return Buffer.concat([iv, authTag, encrypted]).toString("base64");
}

/**
 * Decrypts a string produced by `encrypt`.
 * @throws {TokenDecryptionError} if the payload can't be decrypted/authenticated.
 */
export function decrypt(payload: string): string {
  const key = getKey();

  try {
    const data = Buffer.from(payload, "base64");

    const iv = data.subarray(0, IV_LENGTH);
    const authTag = data.subarray(IV_LENGTH, IV_LENGTH + AUTH_TAG_LENGTH);
    const ciphertext = data.subarray(IV_LENGTH + AUTH_TAG_LENGTH);

    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    decipher.setAuthTag(authTag);

    const decrypted = Buffer.concat([
      decipher.update(ciphertext),
      decipher.final(),
    ]);

    return decrypted.toString("utf8");
  } catch (cause) {
    throw new TokenDecryptionError();
  }
}
