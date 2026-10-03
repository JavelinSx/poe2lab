// Not following an author any more.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  await run(e, "DELETE FROM follows WHERE user_id = ? AND author_id = (SELECT id FROM users WHERE nick = ? COLLATE NOCASE)", user.id, getRouterParam(e, "nick") || "");
  return { following: false };
});
