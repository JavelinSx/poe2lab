// Cloudflare's bindings as the API uses them: D1 (the database) and R2 (the builds' packages). On Workers they come
// with the request; in `npm run dev` nitro-cloudflare-dev gives local copies (wrangler.toml, .wrangler/).
import type { H3Event } from "h3";

export interface D1Result<T> { results?: T[]; success: boolean; meta?: { changes?: number } }
export interface D1Prepared {
  bind(...args: unknown[]): D1Prepared;
  all<T = Record<string, unknown>>(): Promise<D1Result<T>>;
  first<T = Record<string, unknown>>(): Promise<T | null>;
  run(): Promise<D1Result<never>>;
}
export interface D1Database { prepare(sql: string): D1Prepared; batch(list: D1Prepared[]): Promise<D1Result<unknown>[]> }
export interface R2Object { text(): Promise<string> }
export interface R2Bucket {
  get(key: string): Promise<R2Object | null>;
  put(key: string, value: string, opts?: { httpMetadata?: { contentType?: string } }): Promise<unknown>;
  delete(key: string | string[]): Promise<void>;
}
export interface Env { DB: D1Database; PACKAGES: R2Bucket }

export function cf(event: H3Event): Env {
  const env = (event.context as unknown as { cloudflare?: { env?: Env } }).cloudflare?.env;
  if (!env?.DB || !env?.PACKAGES) throw createError({ statusCode: 503, statusMessage: "База сайта недоступна" });
  return env;
}

// the database in three words: all rows, the first row, a change
export const all = async <T>(e: H3Event, sql: string, ...args: unknown[]) => (await cf(e).DB.prepare(sql).bind(...args).all<T>()).results ?? [];
export const first = <T>(e: H3Event, sql: string, ...args: unknown[]) => cf(e).DB.prepare(sql).bind(...args).first<T>();
export const run = (e: H3Event, sql: string, ...args: unknown[]) => cf(e).DB.prepare(sql).bind(...args).run();

export const now = () => Math.floor(Date.now() / 1000);

// a random id or secret: letters and digits without the ones people mix up when they read a code aloud
const ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";
export function randomId(n = 10, alphabet = ALPHABET) {
  const bytes = crypto.getRandomValues(new Uint8Array(n));
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
}
export async function sha256(text: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(d), (b) => b.toString(16).padStart(2, "0")).join("");
}
export const parseJson = <T>(s: unknown, fallback: T): T => { try { return typeof s === "string" ? JSON.parse(s) as T : fallback; } catch { return fallback; } };
