// All the signed-in one's notifications read.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  await run(e, "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", now(), user.id);
  return { ok: true };
});
