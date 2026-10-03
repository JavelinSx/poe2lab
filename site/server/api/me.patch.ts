// The signed-in one changes what the site shows of them: nick, about, links (Twitch, YouTube), language, which
// notifications. Only the fields sent change.
import { nickOk } from "~~/shared/catalog";
import { LINK_KINDS, linkUrl, type UserLink } from "~~/shared/api";

export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const b = await readBody<{ nick?: string; bio?: string; links?: UserLink[]; lang?: string; notify?: Record<string, unknown> }>(e);
  const sets: string[] = [], args: unknown[] = [];
  if (b.nick !== undefined) {
    const nick = String(b.nick).trim();
    if (!nickOk(nick)) throw createError({ statusCode: 400, message: "Ник не подходит: 3–24 знака, буквы, цифры, _ и -" });
    const had = await first<{ id: string }>(e, "SELECT id FROM users WHERE nick = ? COLLATE NOCASE", nick);
    if (had && had.id !== user.id) throw createError({ statusCode: 409, message: "Этот ник занят" });
    sets.push("nick = ?"); args.push(nick);
  }
  if (b.bio !== undefined) {
    const bio = String(b.bio).replace(/\r/g, "").trim();
    if (bio.length > 300) throw createError({ statusCode: 400, message: "«О себе» — до 300 знаков" });
    sets.push("bio = ?"); args.push(bio);
  }
  if (b.links !== undefined) {
    const links: UserLink[] = [];
    for (const l of Array.isArray(b.links) ? b.links.slice(0, 4) : []) {
      if (!l || !(l.kind in LINK_KINDS) || !String(l.url ?? "").trim()) continue;
      const url = linkUrl(l.kind, String(l.url));
      if (!url) throw createError({ statusCode: 400, message: `Ссылка на ${LINK_KINDS[l.kind].label} не похожа на ${LINK_KINDS[l.kind].hosts[0]}/…` });
      links.push({ kind: l.kind, url });
    }
    sets.push("links = ?"); args.push(JSON.stringify(links));
  }
  if (b.lang !== undefined) { sets.push("lang = ?"); args.push(b.lang === "en" ? "en" : "ru"); }
  if (b.notify !== undefined) {
    const n = b.notify ?? {};
    sets.push("notify = ?"); args.push(JSON.stringify({ reviews: n.reviews !== false, replies: n.replies !== false, follows: n.follows !== false }));
  }
  if (sets.length) await run(e, `UPDATE users SET ${sets.join(", ")} WHERE id = ?`, ...args, user.id);
  return { ok: true };
});
