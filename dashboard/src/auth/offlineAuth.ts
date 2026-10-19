import type { TokenPair, User } from "../api/types";

/* ------------------------------------------------------------------------------------------------
 * Offline sign-in for the field tool. After a successful online sign-in the session (token pair and
 * profile) is kept on the device, encrypted with a key derived from the officer's password (PBKDF2 →
 * AES-GCM). Without network the same username and password unlock it, so the officer can sign out and
 * sign in again in the field. Nothing readable is stored: a wrong password simply fails to decrypt.
 * ---------------------------------------------------------------------------------------------- */

const KEY = "fm_offline_auth";
const ITERATIONS = 120_000;

type Entry = { salt: string; iv: string; data: string; saved_at: string };
type Payload = { tokens: TokenPair; user: User };

const enc = new TextEncoder();
const dec = new TextDecoder();
const b64 = (b: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(b)));
const unb64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

export const offlineAuthAvailable = () => typeof crypto !== "undefined" && !!crypto.subtle;

function readAll(): Record<string, Entry> {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}") as Record<string, Entry>; } catch { return {}; }
}
function writeAll(all: Record<string, Entry>) {
  try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* storage full or private mode */ }
}

async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", enc.encode(password.normalize("NFKC")), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt: salt as BufferSource, iterations: ITERATIONS, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

/** Keep this session on the device for offline sign-in with the given password. */
export async function rememberOffline(username: string, password: string, tokens: TokenPair, user: User): Promise<void> {
  if (!offlineAuthAvailable()) return;
  try {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const payload: Payload = { tokens: { access_token: tokens.access_token, refresh_token: tokens.refresh_token } as TokenPair, user };
    const data = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv as BufferSource }, key, enc.encode(JSON.stringify(payload)));
    const all = readAll();
    all[username.trim().toLowerCase()] = { salt: b64(salt), iv: b64(iv), data: b64(data), saved_at: new Date().toISOString() };
    // keep the last three officers of this device
    const keep = Object.entries(all).sort((a, b) => b[1].saved_at.localeCompare(a[1].saved_at)).slice(0, 3);
    writeAll(Object.fromEntries(keep));
  } catch { /* no secure context: offline sign-in simply not available */ }
}

/** Is an offline sign-in saved for this username? */
export function hasOfflineSession(username: string): boolean {
  return !!readAll()[username.trim().toLowerCase()];
}

/** Unlock the saved session with the password; null when none is saved or the password is wrong. */
export async function signInOffline(username: string, password: string): Promise<Payload | null> {
  if (!offlineAuthAvailable()) return null;
  const e = readAll()[username.trim().toLowerCase()];
  if (!e) return null;
  try {
    const key = await deriveKey(password, unb64(e.salt));
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(e.iv) as BufferSource }, key, unb64(e.data) as BufferSource);
    return JSON.parse(dec.decode(plain)) as Payload;
  } catch { return null; }
}

/** Forget the saved session of a username (an account the server rejected). */
export function forgetOffline(username: string) {
  const all = readAll();
  delete all[username.trim().toLowerCase()];
  writeAll(all);
}
