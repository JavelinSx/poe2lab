import { nickOk } from "~~/shared/catalog";

// Whether a nick fits and is free (the welcome page and the settings ask while it is typed).
export default defineEventHandler(async (e) => {
  const n = String(getQuery(e).n ?? "").trim();
  if (!nickOk(n)) return { ok: false, free: false };
  const me = await sessionUser(e);
  const had = await first<{ id: string }>(e, "SELECT id FROM users WHERE nick = ? COLLATE NOCASE", n);
  return { ok: true, free: !had || had.id === me?.id };
});
