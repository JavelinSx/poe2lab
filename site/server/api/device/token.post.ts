// The app takes its token once the player allowed it (it asks every few seconds): 202 while waiting, 410 when
// declined or expired. The token is given once; only its hash is kept.
export default defineEventHandler(async (e) => {
  const { device } = await readBody<{ device: string }>(e);
  const d = await first<{ code: string; name: string; user_id: string | null; state: string; expires_at: number }>(e,
    "SELECT code, name, user_id, state, expires_at FROM device_codes WHERE device_id = ?", String(device || ""));
  if (!d || d.expires_at < now() || d.state === "declined" || d.state === "taken") {
    throw createError({ statusCode: 410, statusMessage: d?.state === "declined" ? "Игрок отклонил подключение" : "Код истёк — начни заново" });
  }
  if (d.state === "pending" || !d.user_id) { setResponseStatus(e, 202); return { pending: true }; }
  const token = randomId(48);
  await cf(e).DB.batch([
    cf(e).DB.prepare("INSERT INTO app_tokens (id, user_id, token_hash, name, created_at) VALUES (?, ?, ?, ?, ?)").bind(randomId(10), d.user_id, await sha256(token), d.name, now()),
    cf(e).DB.prepare("UPDATE device_codes SET state = 'taken' WHERE code = ?").bind(d.code),
  ]);
  const u = await first<{ nick: string }>(e, "SELECT nick FROM users WHERE id = ?", d.user_id);
  return { token, nick: u?.nick };
});
