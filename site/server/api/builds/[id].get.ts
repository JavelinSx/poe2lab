// A build's page: its card, what the app published (the package, from R2), the reviews' summary, its author. A build
// taken off the site answers 410 with its author (the page leads to the author's other builds); the author sees it.
import type { BuildPackage } from "~~/shared/package";

export default defineEventHandler(async (e) => {
  const id = getRouterParam(e, "id") || "";
  const row = await first<CardRow & { package_key: string; author_id: string; description: string }>(e,
    `SELECT ${CARD_COLUMNS}, b.package_key, b.author_id, b.description FROM builds b JOIN users u ON u.id = b.author_id WHERE b.id = ?`, id);
  if (!row || row.status === "removed") throw createError({ statusCode: 404, statusMessage: "Такого билда нет" });
  const me = await sessionUser(e);
  if (row.status === "hidden" && me?.id !== row.author_id) throw createError({ statusCode: 410, statusMessage: "Автор снял билд с публикации", data: { author: row.nick } });
  const obj = await cf(e).PACKAGES.get(row.package_key);
  if (!obj) throw createError({ statusCode: 500, statusMessage: "Пакет билда потерян" });
  const pkg = JSON.parse(await obj.text()) as BuildPackage;
  const [dist, crit, author] = await Promise.all([
    all<{ stars: number; n: number }>(e, "SELECT stars, COUNT(*) AS n FROM reviews WHERE build_id = ? AND status = 'visible' GROUP BY stars", id),
    all<{ crit: string }>(e, "SELECT crit FROM reviews WHERE build_id = ? AND status = 'visible' AND crit != '{}'", id),
    first<{ builds: number; followers: number; rating: number | null; bio: string; links: string }>(e, `SELECT
      (SELECT COUNT(*) FROM builds WHERE author_id = ? AND status = 'published') AS builds,
      (SELECT COUNT(*) FROM follows WHERE author_id = ?) AS followers,
      (SELECT SUM(rating_sum) * 1.0 / NULLIF(SUM(rating_n), 0) FROM builds WHERE author_id = ? AND status = 'published') AS rating,
      bio, links FROM users WHERE id = ?`, row.author_id, row.author_id, row.author_id, row.author_id),
  ]);
  // the criteria's averages, over the reviews that gave them
  const sums: Record<string, [number, number]> = {};
  for (const r of crit) for (const [k, v] of Object.entries(parseJson<Record<string, number>>(r.crit, {}))) {
    if (typeof v === "number" && v >= 1 && v <= 5) { sums[k] = sums[k] || [0, 0]; sums[k][0] += v; sums[k][1] += 1; }
  }
  // a look, counted once a visitor a day would need a store; for now every page view
  if (me?.id !== row.author_id) await run(e, "UPDATE builds SET views = views + 1 WHERE id = ?", id);
  return {
    card: toCard(row),
    page: { description: row.description, cards: pkg.cards, numbers: pkg.numbers, main: pkg.main, groups: pkg.groups, gear: pkg.gear,
      gearSummary: pkg.gearSummary, skillTags: pkg.skillTags ?? [] },
    reviews: { n: row.rating_n, avg: row.rating_n ? row.rating_sum / row.rating_n : 0,
      dist: [5, 4, 3, 2, 1].map((s) => [s, dist.find((d) => d.stars === s)?.n ?? 0]),
      crit: Object.fromEntries(Object.entries(sums).map(([k, [s, n]]) => [k, s / n])) },
    author: { nick: row.nick, hue: row.hue, avatar: row.avatar, builds: author?.builds ?? 0, followers: author?.followers ?? 0,
      rating: author?.rating ?? 0, links: parseJson(author?.links, []) },
    mine: me?.id === row.author_id,
  };
});
