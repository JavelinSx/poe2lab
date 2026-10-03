// Who asks: a person on the site (a session cookie after signing in with Discord) or the app (its token, Bearer).
import type { H3Event } from "h3";

export interface User { id: string; nick: string; hue: number; avatar: string | null; role: "user" | "mod" | "owner"; banned_at: number | null }
const SESSION_DAYS = 30;
const COOKIE = "sid";

export async function sessionUser(e: H3Event): Promise<User | null> {
  const sid = getCookie(e, COOKIE);
  if (!sid) return null;
  return await first<User>(e, `SELECT u.id, u.nick, u.hue, u.avatar, u.role, u.banned_at FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.id = ? AND s.expires_at > ? AND u.banned_at IS NULL`, sid, now());
}
export async function requireUser(e: H3Event): Promise<User> {
  const u = await sessionUser(e);
  if (!u) throw createError({ statusCode: 401, message: "Нужно войти" });
  return u;
}
export async function requireRole(e: H3Event, ...roles: User["role"][]): Promise<User> {
  const u = await requireUser(e);
  if (!roles.includes(u.role)) throw createError({ statusCode: 403, message: "Нет прав" });
  return u;
}
export async function startSession(e: H3Event, userId: string) {
  const sid = randomId(32);
  await run(e, "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)", sid, userId, now() + SESSION_DAYS * 86400, now());
  setCookie(e, COOKIE, sid, { httpOnly: true, sameSite: "lax", secure: !import.meta.dev, path: "/", maxAge: SESSION_DAYS * 86400 });
}
export async function endSession(e: H3Event) {
  const sid = getCookie(e, COOKIE);
  if (sid) await run(e, "DELETE FROM sessions WHERE id = ?", sid);
  deleteCookie(e, COOKIE, { path: "/" });
}

// the app: "Authorization: Bearer <token>"; only the token's hash is kept
export async function appUser(e: H3Event): Promise<User> {
  const h = getHeader(e, "authorization") || "";
  const token = h.startsWith("Bearer ") ? h.slice(7).trim() : "";
  if (!token) throw createError({ statusCode: 401, message: "Приложение не подключено к сайту" });
  const hash = await sha256(token);
  const u = await first<User & { token_id: string }>(e, `SELECT u.id, u.nick, u.hue, u.avatar, u.role, u.banned_at, t.id AS token_id
    FROM app_tokens t JOIN users u ON u.id = t.user_id WHERE t.token_hash = ? AND u.banned_at IS NULL`, hash);
  if (!u) throw createError({ statusCode: 401, message: "Подключение приложения отозвано — подключи заново" });
  await run(e, "UPDATE app_tokens SET last_used_at = ? WHERE id = ?", now(), u.token_id);
  return u;
}
