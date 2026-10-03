// The catalog: builds by the filters and words of the page's address, a page of them, how many there are, and the
// counts beside the chosen class's ascendancies.
export default defineEventHandler(async (e) => {
  const c = readQuery(getQuery(e));
  const w = where(c);
  const from = "FROM builds b JOIN users u ON u.id = b.author_id";
  const [rows, total, ascs] = await Promise.all([
    all<CardRow>(e, `SELECT ${CARD_COLUMNS} ${from} WHERE ${w.sql} ORDER BY ${SORTS[c.sort]} LIMIT ? OFFSET ?`, ...w.args, c.limit, c.offset),
    first<{ n: number }>(e, `SELECT COUNT(*) AS n ${from} WHERE ${w.sql}`, ...w.args),
    c.cls ? (() => { const wa = where(c, "asc"); return all<{ asc: string; n: number }>(e, `SELECT b.asc, COUNT(*) AS n ${from} WHERE ${wa.sql} GROUP BY b.asc`, ...wa.args); })() : [],
  ]);
  return { builds: rows.map(toCard), total: total?.n ?? 0, offset: c.offset, ascendancies: Object.fromEntries(ascs.map((a) => [a.asc, a.n])) };
});
