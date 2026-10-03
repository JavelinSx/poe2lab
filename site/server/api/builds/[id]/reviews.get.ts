// A build's reviews, sorted (helpful, new, high, low), ten at a time; each with whether the one asking found it helpful.
import type { ClassKey } from "~~/shared/catalog";
import type { ReviewItem, ReviewsData } from "~~/shared/api";

const ORDER: Record<string, string> = { helpful: "r.helpful_n DESC, r.created_at DESC", new: "r.created_at DESC", high: "r.stars DESC, r.created_at DESC", low: "r.stars ASC, r.created_at DESC" };

export default defineEventHandler(async (e) => {
  const id = getRouterParam(e, "id") || "";
  const q = getQuery(e);
  const order = ORDER[String(q.sort)] ?? ORDER.helpful;
  const offset = Math.max(0, Number(q.offset) || 0);
  const me = await sessionUser(e);
  const rows = await all<{ id: string; nick: string; hue: number; avatar: string | null; user_id: string; stars: number; crit: string; text: string;
    char_cls: string | null; char_level: number | null; helpful_n: number; reply: string | null; reply_at: number | null; created_at: number; voted: number }>(e,
    `SELECT r.id, u.nick, u.hue, u.avatar, r.user_id, r.stars, r.crit, r.text, r.char_cls, r.char_level, r.helpful_n, r.reply, r.reply_at, r.created_at,
      EXISTS (SELECT 1 FROM review_votes v WHERE v.review_id = r.id AND v.user_id = ?) AS voted
     FROM reviews r JOIN users u ON u.id = r.user_id WHERE r.build_id = ? AND r.status = 'visible' ORDER BY ${order} LIMIT 10 OFFSET ?`, me?.id ?? "", id, offset);
  const mine = me ? await first<{ stars: number; crit: string; text: string; char_cls: string | null; char_level: number | null }>(e,
    "SELECT stars, crit, text, char_cls, char_level FROM reviews WHERE build_id = ? AND user_id = ?", id, me.id) : null;
  return {
    items: rows.map((r): ReviewItem => ({ id: r.id, nick: r.nick, hue: r.hue, avatar: r.avatar, stars: r.stars, crit: parseJson(r.crit, {}), text: r.text,
      cls: r.char_cls as ClassKey | null, level: r.char_level, helpful: r.helpful_n, voted: Boolean(r.voted), own: r.user_id === me?.id,
      reply: r.reply ? { text: r.reply, at: r.reply_at ?? r.created_at } : null, at: r.created_at })),
    mine: mine ? { ...mine, char_cls: mine.char_cls as ClassKey | null, crit: parseJson(mine.crit, {}) } : null,
  } satisfies ReviewsData;
});
