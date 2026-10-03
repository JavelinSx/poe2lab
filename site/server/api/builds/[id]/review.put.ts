// One review per account, written or changed: stars (needed), criteria (if given), the text, the reviewer's
// character. The build's author cannot review their own build; the build's rating follows; the author is notified.
import { CLASS_KEYS } from "~~/shared/catalog";

const CRIT = ["dmg", "tank", "budget", "ease"];

export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  const b = await readBody<{ stars: number; crit?: Record<string, number>; text: string; cls?: string; level?: number }>(e);
  const stars = Math.round(Number(b.stars));
  if (!(stars >= 1 && stars <= 5)) throw createError({ statusCode: 400, statusMessage: "Оценка — от 1 до 5" });
  const text = String(b.text ?? "").replace(/\r/g, "").trim();
  if (!text || text.length > 1000) throw createError({ statusCode: 400, statusMessage: "Отзыв — от 1 до 1000 знаков" });
  const crit = Object.fromEntries(Object.entries(b.crit ?? {}).filter(([k, v]) => CRIT.includes(k) && Number.isInteger(v) && v >= 1 && v <= 5));
  const cls = b.cls && CLASS_KEYS.includes(b.cls as never) ? b.cls : null;
  const level = Number.isInteger(b.level) && b.level! >= 1 && b.level! <= 100 ? b.level! : null;
  const build = await first<{ author_id: string }>(e, "SELECT author_id FROM builds WHERE id = ? AND status = 'published'", id);
  if (!build) throw createError({ statusCode: 404, statusMessage: "Такого билда нет" });
  if (build.author_id === user.id) throw createError({ statusCode: 403, statusMessage: "На свой билд отзыв не оставить — отвечай под отзывами" });
  const old = await first<{ id: string; stars: number }>(e, "SELECT id, stars FROM reviews WHERE build_id = ? AND user_id = ?", id, user.id);
  const t = now();
  if (old) {
    await cf(e).DB.batch([
      cf(e).DB.prepare("UPDATE reviews SET stars = ?, crit = ?, text = ?, char_cls = ?, char_level = ?, updated_at = ? WHERE id = ?")
        .bind(stars, JSON.stringify(crit), text, cls, level, t, old.id),
      cf(e).DB.prepare("UPDATE builds SET rating_sum = rating_sum - ? + ? WHERE id = ?").bind(old.stars, stars, id),
    ]);
    return { id: old.id, updated: true };
  }
  const rid = randomId(10);
  await cf(e).DB.batch([
    cf(e).DB.prepare(`INSERT INTO reviews (id, build_id, user_id, stars, crit, text, char_cls, char_level, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).bind(rid, id, user.id, stars, JSON.stringify(crit), text, cls, level, t, t),
    cf(e).DB.prepare("UPDATE builds SET rating_sum = rating_sum + ?, rating_n = rating_n + 1 WHERE id = ?").bind(stars, id),
    cf(e).DB.prepare("INSERT INTO notifications (id, user_id, kind, actor_id, build_id, review_id, created_at) VALUES (?, ?, 'review', ?, ?, ?, ?)")
      .bind(randomId(12), build.author_id, user.id, id, rid, t),
  ]);
  return { id: rid, updated: false };
});
