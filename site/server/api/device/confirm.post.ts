// The player, signed in, allows the app that shows this code to publish for them - or declines it.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const { code, allow } = await readBody<{ code: string; allow: boolean }>(e);
  const c = String(code || "").toUpperCase();
  const d = await first<{ state: string; expires_at: number }>(e, "SELECT state, expires_at FROM device_codes WHERE code = ?", c);
  if (!d || d.expires_at < now() || d.state !== "pending") throw createError({ statusCode: 404, statusMessage: "Код не найден или истёк — попроси новый в приложении" });
  await run(e, "UPDATE device_codes SET state = ?, user_id = ? WHERE code = ?", allow ? "allowed" : "declined", allow ? user.id : null, c);
  return { ok: true, state: allow ? "allowed" : "declined" };
});
