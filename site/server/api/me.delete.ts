// The account deleted for good: its builds (and their packages), reviews, votes, favourites, follows, sessions and
// apps. The ratings and "helpful" counts it took part in are taken back first, in the same batch.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const builds = await all<{ id: string; version: number }>(e, "SELECT id, version FROM builds WHERE author_id = ?", user.id);
  const db = cf(e).DB;
  await db.batch([
    db.prepare(`UPDATE builds SET rating_sum = rating_sum - (SELECT r.stars FROM reviews r WHERE r.build_id = builds.id AND r.user_id = ?),
      rating_n = rating_n - 1 WHERE id IN (SELECT build_id FROM reviews WHERE user_id = ?)`).bind(user.id, user.id),
    db.prepare("UPDATE reviews SET helpful_n = helpful_n - 1 WHERE id IN (SELECT review_id FROM review_votes WHERE user_id = ?)").bind(user.id),
    db.prepare("DELETE FROM users WHERE id = ?").bind(user.id),
  ]);
  const keys = builds.flatMap((b) => [`builds/${b.id}/${b.version}.json`, `builds/${b.id}/${b.version - 1}.json`]);
  for (let i = 0; i < keys.length; i += 1000) await cf(e).PACKAGES.delete(keys.slice(i, i + 1000));
  deleteCookie(e, "sid", { path: "/" });
  return { ok: true };
});
