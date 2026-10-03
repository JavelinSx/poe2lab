// The cabinet: the author's builds, published and taken off, each with its numbers and new reviews.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const rows = await all<CardRow & { fresh: number }>(e, `SELECT ${CARD_COLUMNS},
      (SELECT COUNT(*) FROM notifications n WHERE n.build_id = b.id AND n.user_id = ? AND n.kind = 'review' AND n.read_at IS NULL) AS fresh
    FROM builds b JOIN users u ON u.id = b.author_id WHERE b.author_id = ? AND b.status != 'removed' ORDER BY b.updated_at DESC`, user.id, user.id);
  return rows.map((r) => ({ ...toCard(r), newReviews: r.fresh }));
});
