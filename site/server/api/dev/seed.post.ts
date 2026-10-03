// Development and the local test server only: the design's example builds, authors and reviews put into the local
// database through the same publishing as the app's, so the pages have something to show. The real site answers 404.
import { BUILDS } from "~~/mock/builds";
import { PAGES } from "~~/mock/page";
import { CURRENT_PATCH } from "~~/shared/catalog";
import type { BuildPackage } from "~~/shared/package";

export default defineEventHandler(async (e) => {
  requireDev(e);
  const users: Record<string, string> = {};
  const userOf = async (nick: string, hue: number, role = "user") => {
    if (users[nick]) return users[nick];
    const had = await first<{ id: string }>(e, "SELECT id FROM users WHERE nick = ? COLLATE NOCASE", nick);
    const id = had?.id ?? randomId(10);
    if (!had) await run(e, "INSERT INTO users (id, nick, hue, role, created_at) VALUES (?, ?, ?, ?, ?)", id, nick, hue, role, now() - 86400 * 200);
    return (users[nick] = id);
  };
  const ids: Record<string, string> = {};
  for (const m of BUILDS) {
    const author = await userOf(m.author, m.hue, m.author === "frostmonk" ? "owner" : "user");
    const page = PAGES[m.id];
    const pkg: BuildPackage = {
      v: 1, app: "poe2lab dev", key: `seed-${m.id}`, patch: m.patch || CURRENT_PATCH, title: m.title, tags: m.tags, cls: m.cls, asc: m.asc,
      mainSkill: m.skill, skillIcon: m.icon, dmg: m.dmg, weapon: m.weapon, cover: m.cover,
      numbers: page?.numbers ?? { dps: m.dps, life: m.life, es: m.es, res: { fire: 75, cold: 75, light: 75, chaos: 0 }, defence: { value: m.es || m.life, kind: m.es ? "энергощит" : "броня" } },
      description: page?.description ?? "", cards: page?.cards ?? {},
      main: page?.main ?? { name: m.skill, img: m.icon, supports: [] }, groups: page?.groups ?? [], gear: page?.gear ?? [], gearSummary: page?.gearSummary,
      pob: "eNrtvWtz2ziyMPx5/Stw8u2+/",
    };
    ids[m.id] = (await publish(e, author, pkg)).id;
    await run(e, "UPDATE builds SET opens = ?, updated_at = ? WHERE id = ?", m.opens, Math.floor(new Date(m.updated).getTime() / 1000), ids[m.id]);
  }
  // reviews: the example page's own, and stars enough to make each build's rating
  let made = 0;
  for (const m of BUILDS) {
    const page = PAGES[m.id];
    const reviewers = page?.reviews.items ?? [];
    for (const r of reviewers) {
      const uid = await userOf(r.nick, r.hue);
      const had = await first(e, "SELECT 1 FROM reviews WHERE build_id = ? AND user_id = ?", ids[m.id], uid);
      if (had) continue;
      await run(e, `INSERT INTO reviews (id, build_id, user_id, stars, crit, text, char_cls, char_level, helpful_n, reply, reply_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, randomId(10), ids[m.id], uid, r.stars,
      JSON.stringify(Object.fromEntries((r.crit ?? []).map(([k, v]) => [{ "Урон": "dmg", "Живучесть": "tank", "Бюджет": "budget", "Лёгкость": "ease" }[k] ?? k, v]))),
      r.text, r.cls, r.level, r.helpful, r.reply?.text ?? null, r.reply ? now() : null, now() - 86400 * 3, now());
      made++;
    }
    const want = Math.max(m.reviews - reviewers.length, 0);
    const sum = Math.round(m.rating * m.reviews) - reviewers.reduce((s, r) => s + r.stars, 0);
    await run(e, "UPDATE builds SET rating_sum = (SELECT COALESCE(SUM(stars), 0) FROM reviews WHERE build_id = ?) + ?, rating_n = (SELECT COUNT(*) FROM reviews WHERE build_id = ?) + ? WHERE id = ?",
      ids[m.id], want ? sum : 0, ids[m.id], want, ids[m.id]);
  }
  return { builds: Object.keys(ids).length, reviews: made, ids };
});
