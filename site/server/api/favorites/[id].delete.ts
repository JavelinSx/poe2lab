// A build out of the signed-in one's favourites.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  await run(e, "DELETE FROM favorites WHERE user_id = ? AND build_id = ?", user.id, getRouterParam(e, "id") || "");
  return { favorite: false };
});
