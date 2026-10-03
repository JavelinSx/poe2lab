// An author's public page: who, links, numbers, their builds, the latest reviews on them.
export default defineEventHandler(async (e) => {
  const nick = String(getRouterParam(e, "nick") || "");
  const u = await first<{ id: string; nick: string; hue: number; avatar: string | null; bio: string; links: string; created_at: number }>(e,
    "SELECT id, nick, hue, avatar, bio, links, created_at FROM users WHERE nick = ? COLLATE NOCASE AND banned_at IS NULL", nick);
  if (!u) throw createError({ statusCode: 404, statusMessage: "Такого автора нет" });
  const me = await sessionUser(e);
  const [builds, reviews, followers, following] = await Promise.all([
    all<CardRow>(e, `SELECT ${CARD_COLUMNS} FROM builds b JOIN users u ON u.id = b.author_id WHERE b.author_id = ? AND b.status = 'published'`, u.id),
    all<{ id: string; build_id: string; nick: string; hue: number; stars: number; text: string; char_cls: string | null; char_level: number | null;
      helpful_n: number; reply: string | null; reply_at: number | null; created_at: number }>(e,
      `SELECT r.id, r.build_id, ru.nick, ru.hue, r.stars, r.text, r.char_cls, r.char_level, r.helpful_n, r.reply, r.reply_at, r.created_at
       FROM reviews r JOIN builds b ON b.id = r.build_id JOIN users ru ON ru.id = r.user_id
       WHERE b.author_id = ? AND b.status = 'published' AND r.status = 'visible' ORDER BY r.created_at DESC LIMIT 5`, u.id),
    first<{ n: number }>(e, "SELECT COUNT(*) AS n FROM follows WHERE author_id = ?", u.id),
    me ? first(e, "SELECT 1 FROM follows WHERE user_id = ? AND author_id = ?", me.id, u.id) : null,
  ]);
  const total = await first<{ n: number }>(e, "SELECT COUNT(*) AS n FROM reviews r JOIN builds b ON b.id = r.build_id WHERE b.author_id = ? AND r.status = 'visible'", u.id);
  return {
    nick: u.nick, hue: u.hue, avatar: u.avatar, bio: u.bio, links: parseJson(u.links, []), since: u.created_at,
    followers: followers?.n ?? 0, following: Boolean(following), builds: builds.map(toCard),
    reviews: reviews.map((r) => ({ id: r.id, build: r.build_id, nick: r.nick, hue: r.hue, stars: r.stars, text: r.text, cls: r.char_cls, level: r.char_level,
      helpful: r.helpful_n, reply: r.reply ? { text: r.reply, at: r.reply_at } : null, at: r.created_at })),
    reviewsTotal: total?.n ?? 0,
  };
});
