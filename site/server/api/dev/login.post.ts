// Development only: sign in as a nick (made if new) without Discord. The real site answers 404 here.
export default defineEventHandler(async (e) => {
  if (!import.meta.dev) throw createError({ statusCode: 404 });
  const { nick, role } = await readBody<{ nick: string; role?: string }>(e);
  const name = String(nick || "").slice(0, 24);
  if (!/^[A-Za-zА-Яа-яЁё0-9_-]{3,24}$/.test(name)) throw createError({ statusCode: 400, statusMessage: "Ник — 3–24 знака" });
  let u = await first<{ id: string }>(e, "SELECT id FROM users WHERE nick = ? COLLATE NOCASE", name);
  if (!u) {
    u = { id: randomId(10) };
    await run(e, "INSERT INTO users (id, nick, hue, role, created_at) VALUES (?, ?, ?, ?, ?)", u.id, name, Math.floor(Math.random() * 360),
      ["user", "mod", "owner"].includes(String(role)) ? role : "user", now());
  }
  await startSession(e, u.id);
  return { ok: true };
});
