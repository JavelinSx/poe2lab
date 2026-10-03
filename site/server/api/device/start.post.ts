// The app asks to be connected: a code for the player to compare on the site (10 minutes), and a secret only the
// app keeps to take its token once the player allows it.
const CODE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";

export default defineEventHandler(async (e) => {
  const { name } = await readBody<{ name?: string }>(e);
  const label = String(name || "poe2lab").replace(/[^\p{L}\p{N} ._()-]/gu, "").slice(0, 60) || "poe2lab";
  await run(e, "DELETE FROM device_codes WHERE expires_at < ?", now());
  const code = randomId(6, CODE);
  const device = randomId(40);
  await run(e, "INSERT INTO device_codes (code, device_id, name, expires_at) VALUES (?, ?, ?, ?)", code, device, label, now() + 600);
  return { code, device, verify: `/connect?code=${code}`, expiresIn: 600 };
});
