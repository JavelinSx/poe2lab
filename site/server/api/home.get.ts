// The main page in one answer: how many builds each class has, the shelves (popular, for the league's start, new),
// the best authors.
const SHELF = `SELECT ${CARD_COLUMNS} FROM builds b JOIN users u ON u.id = b.author_id WHERE b.status = 'published'`;

export default defineEventHandler(async (e) => {
  const [classes, popular, start, fresh, authors] = await Promise.all([
    all<{ cls: string; n: number }>(e, "SELECT cls, COUNT(*) AS n FROM builds WHERE status = 'published' GROUP BY cls"),
    all<CardRow>(e, `${SHELF} ORDER BY b.opens DESC LIMIT 4`),
    all<CardRow>(e, `${SHELF} AND b.tags LIKE '%"старт лиги"%' ORDER BY ${ORDER_BY.rating} LIMIT 4`),
    all<CardRow>(e, `${SHELF} ORDER BY b.updated_at DESC LIMIT 4`),
    all<{ nick: string; hue: number; avatar: string | null; classes: string; rating: number; builds: number }>(e,
      `SELECT u.nick, u.hue, u.avatar, GROUP_CONCAT(DISTINCT b.cls) AS classes, SUM(b.rating_sum) * 1.0 / SUM(b.rating_n) AS rating, COUNT(*) AS builds
       FROM builds b JOIN users u ON u.id = b.author_id WHERE b.status = 'published' GROUP BY u.id HAVING SUM(b.rating_n) > 0
       ORDER BY rating DESC LIMIT 6`),
  ]);
  return {
    classes: Object.fromEntries(classes.map((c) => [c.cls, c.n])),
    shelves: { popular: popular.map(toCard), start: start.map(toCard), fresh: fresh.map(toCard) },
    authors: authors.map((a) => ({ ...a, classes: (a.classes || "").split(",").filter(Boolean) })),
  };
});
