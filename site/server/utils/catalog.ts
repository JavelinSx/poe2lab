// The catalog's query from the page's address: filters, search words, sort, a page of results. Values always go as
// parameters, never into the SQL text.
import { CLASS_KEYS, CURRENT_PATCH, DMG_KEYS, TAG_NAMES, WEAPONS, knownWord, norm } from "~~/shared/catalog";

export const PAGE = 24;
export const SORTS: Record<string, string> = {
  rating: "(CASE WHEN b.rating_n > 0 THEN (b.rating_sum + 4.0 * 3) / (b.rating_n + 3) ELSE 0 END) DESC, b.rating_n DESC",
  popular: "b.opens DESC", new: "b.updated_at DESC", dps: "b.dps DESC",
};

export interface CatalogQuery {
  cls?: string; asc: string[]; dmg: string[]; weapon: string[]; tag: string[]; patch: "current" | "all"; q: string;
  sort: string; offset: number; limit: number; author?: string;
}

const list = (v: unknown) => (Array.isArray(v) ? v : v ? [v] : []).map(String).filter(Boolean).slice(0, 20);
export function readQuery(q: Record<string, unknown>): CatalogQuery {
  return {
    cls: CLASS_KEYS.includes(String(q.cls) as never) ? String(q.cls) : undefined,
    asc: list(q.asc).map((x) => x.slice(0, 40)), dmg: list(q.dmg).filter((x) => DMG_KEYS.includes(x as never)),
    weapon: list(q.weapon).filter((x) => WEAPONS.includes(x)), tag: list(q.tag).filter((x) => TAG_NAMES.includes(x)),
    patch: q.patch === "all" ? "all" : "current", q: String(q.q || "").slice(0, 120),
    sort: SORTS[String(q.sort)] ? String(q.sort) : "rating",
    offset: Math.max(0, Math.min(10_000, Number(q.offset) || 0)), limit: Math.max(1, Math.min(48, Number(q.limit) || PAGE)),
    author: q.author ? String(q.author).slice(0, 24) : undefined,
  };
}

// a word for LIKE, its % and _ taken literally
const like = (w: string) => `%${w.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;

/** WHERE ... and its parameters; `skip` leaves one filter out (the counts beside a choice). */
export function where(c: CatalogQuery, skip?: "asc") {
  const parts = ["b.status = 'published'"], args: unknown[] = [];
  if (c.cls) { parts.push("b.cls = ?"); args.push(c.cls); }
  if (c.asc.length && skip !== "asc") { parts.push(`b.asc IN (${c.asc.map(() => "?").join(", ")})`); args.push(...c.asc); }
  if (c.dmg.length) { parts.push(`b.dmg IN (${c.dmg.map(() => "?").join(", ")})`); args.push(...c.dmg); }
  if (c.weapon.length) { parts.push(`b.weapon IN (${c.weapon.map(() => "?").join(", ")})`); args.push(...c.weapon); }
  for (const t of c.tag) { parts.push("b.tags LIKE ? ESCAPE '\\'"); args.push(like(`"${t}"`)); }
  if (c.patch === "current") { parts.push("b.patch = ?"); args.push(CURRENT_PATCH); }
  if (c.author) { parts.push("u.nick = ? COLLATE NOCASE"); args.push(c.author); }
  for (const w of c.q.split(/\s+/).filter(Boolean).slice(0, 8)) {
    const k = knownWord(w);
    if (k?.kind === "tag") { parts.push("b.tags LIKE ? ESCAPE '\\'"); args.push(like(`"${k.key}"`)); }
    else if (k?.kind === "dmg") { parts.push("b.dmg = ?"); args.push(k.key); }
    else if (k?.kind === "weapon") { parts.push("b.weapon = ?"); args.push(k.key); }
    else if (k?.kind === "cls") { parts.push("b.cls = ?"); args.push(k.key); }
    else { parts.push("b.search LIKE ? ESCAPE '\\'"); args.push(like(norm(w))); }
  }
  return { sql: parts.join(" AND "), args };
}

// a build as its card shows it, from its row
export interface CardRow {
  id: string; title: string; cls: string; asc: string; main_skill: string; skill_icon: string | null; dmg: string; weapon: string;
  dps: number; life: number; es: number; rating_sum: number; rating_n: number; nick: string; hue: number; avatar: string | null;
  patch: string; tags: string; cover: string | null; tint: string | null; opens: number; updated_at: number; status?: string; views?: number;
}
export const CARD_COLUMNS = `b.id, b.title, b.cls, b.asc, b.main_skill, b.skill_icon, b.dmg, b.weapon, b.dps, b.life, b.es, b.rating_sum,
  b.rating_n, u.nick, u.hue, u.avatar, b.patch, b.tags, b.cover, b.tint, b.opens, b.updated_at, b.status, b.views`;
export function toCard(r: CardRow) {
  let tags: string[] = [];
  try { tags = JSON.parse(r.tags); } catch { /* none */ }
  return {
    id: r.id, title: r.title, cls: r.cls, asc: r.asc, skill: r.main_skill, icon: r.skill_icon ?? undefined, dmg: r.tint || r.dmg,
    weapon: r.weapon, dps: r.dps, life: r.life, es: r.es, rating: r.rating_n ? r.rating_sum / r.rating_n : 0, reviews: r.rating_n,
    author: r.nick, hue: r.hue, avatar: r.avatar ?? undefined, patch: r.patch, old: r.patch !== CURRENT_PATCH, tags,
    cover: r.cover ?? "", opens: r.opens, updated: new Date(r.updated_at * 1000).toISOString().slice(0, 10), status: r.status, views: r.views,
  };
}
