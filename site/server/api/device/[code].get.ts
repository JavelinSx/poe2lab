// What the connect page shows of a code: which app asks, whether it is still waiting.
export default defineEventHandler(async (e) => {
  const code = String(getRouterParam(e, "code") || "").toUpperCase();
  const d = await first<{ name: string; state: string; expires_at: number }>(e, "SELECT name, state, expires_at FROM device_codes WHERE code = ?", code);
  if (!d || d.expires_at < now()) throw createError({ statusCode: 404, message: "Код не найден или истёк — попроси новый в приложении" });
  return { name: d.name, state: d.state, expiresIn: d.expires_at - now() };
});
