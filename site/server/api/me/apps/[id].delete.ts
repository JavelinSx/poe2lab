// An app taken off the account: its token stops working (the app asks to connect again).
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  await run(e, "DELETE FROM app_tokens WHERE id = ? AND user_id = ?", getRouterParam(e, "id") || "", user.id);
  return { ok: true };
});
