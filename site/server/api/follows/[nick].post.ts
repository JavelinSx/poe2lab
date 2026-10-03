// Following an author: their new builds come to the notifications (if the follower wants them). Not oneself.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const a = await first<{ id: string }>(e, "SELECT id FROM users WHERE nick = ? COLLATE NOCASE AND banned_at IS NULL", getRouterParam(e, "nick") || "");
  if (!a) throw createError({ statusCode: 404, statusMessage: "Такого автора нет" });
  if (a.id === user.id) throw createError({ statusCode: 400, statusMessage: "На себя не подписаться" });
  await run(e, "INSERT OR IGNORE INTO follows (user_id, author_id, created_at) VALUES (?, ?, ?)", user.id, a.id, now());
  return { following: true };
});
