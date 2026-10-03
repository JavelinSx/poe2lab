// "Helpful": one vote an account, a toggle; not on one's own review.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  const r = await first<{ user_id: string }>(e, "SELECT user_id FROM reviews WHERE id = ? AND status = 'visible'", id);
  if (!r) throw createError({ statusCode: 404, message: "Такого отзыва нет" });
  if (r.user_id === user.id) throw createError({ statusCode: 403, message: "За свой отзыв голосовать нельзя" });
  const had = await first(e, "SELECT 1 FROM review_votes WHERE review_id = ? AND user_id = ?", id, user.id);
  const db = cf(e).DB;
  await db.batch(had
    ? [db.prepare("DELETE FROM review_votes WHERE review_id = ? AND user_id = ?").bind(id, user.id), db.prepare("UPDATE reviews SET helpful_n = helpful_n - 1 WHERE id = ?").bind(id)]
    : [db.prepare("INSERT INTO review_votes (review_id, user_id) VALUES (?, ?)").bind(id, user.id), db.prepare("UPDATE reviews SET helpful_n = helpful_n + 1 WHERE id = ?").bind(id)]);
  const n = await first<{ helpful_n: number }>(e, "SELECT helpful_n FROM reviews WHERE id = ?", id);
  return { voted: !had, helpful: n?.helpful_n ?? 0 };
});
