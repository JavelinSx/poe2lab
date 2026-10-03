// A build into the signed-in one's favourites (again is no change).
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  if (!await first(e, "SELECT 1 FROM builds WHERE id = ? AND status = 'published'", id)) throw createError({ statusCode: 404, message: "Такого билда нет" });
  await run(e, "INSERT OR IGNORE INTO favorites (user_id, build_id, created_at) VALUES (?, ?, ?)", user.id, id, now());
  return { favorite: true };
});
