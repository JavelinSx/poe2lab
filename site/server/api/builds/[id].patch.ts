// The author edits on the site what the site shows of the build: title, tags, cover, tint, description (with the
// game's pieces whose cards the app published). Skills, gear and numbers change only from the app.
import { LIMITS, TOKEN, cardOk, visibleLength, type BuildPackage, type Card } from "~~/shared/package";
import { DMG_KEYS, TAG_NAMES, searchText } from "~~/shared/catalog";

export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  const row = await first<{ author_id: string; package_key: string; main_skill: string; cls: string; asc: string; weapon: string }>(e,
    "SELECT author_id, package_key, main_skill, cls, asc, weapon FROM builds WHERE id = ? AND status != 'removed'", id);
  if (!row) throw createError({ statusCode: 404, message: "Такого билда нет" });
  if (row.author_id !== user.id) throw createError({ statusCode: 403, message: "Это не твой билд" });
  const body = await readBody<{ title?: string; tags?: string[]; cover?: string; tint?: string; description?: string; cards?: Record<string, Card> }>(e);
  const title = String(body.title ?? "").trim();
  if (!title || title.length > LIMITS.title) throw createError({ statusCode: 400, message: `Название — от 1 до ${LIMITS.title} знаков` });
  const tags = Array.isArray(body.tags) ? [...new Set(body.tags.map(String))] : [];
  if (tags.length > LIMITS.tags || tags.some((t) => !TAG_NAMES.includes(t))) throw createError({ statusCode: 400, message: `Теги — до ${LIMITS.tags} из списка` });
  if (body.tint && !DMG_KEYS.includes(body.tint as never)) throw createError({ statusCode: 400, message: "Неизвестный цвет подложки" });
  if (body.cover && !/^[\w-]{1,80}$|^https:\/\/web\.poecdn\.com\/\S{1,300}$/.test(body.cover)) throw createError({ statusCode: 400, message: "Неизвестная обложка" });
  // the description's pieces: the package's cards, and the ones the author added from the site's search
  const pkg = JSON.parse(await (await cf(e).PACKAGES.get(row.package_key))!.text()) as BuildPackage;
  const added = body.cards && typeof body.cards === "object" ? body.cards : {};
  if (Object.keys(added).length > 100 || Object.entries(added).some(([k, c]) => !cardOk(k, c))) throw createError({ statusCode: 400, message: "Неверная карточка иконки" });
  const cards = { ...pkg.cards, ...added };
  if (Object.keys(cards).length > LIMITS.cards) throw createError({ statusCode: 400, message: `Иконок — до ${LIMITS.cards}` });
  const description = String(body.description ?? "").replace(/\r/g, "").trim();
  if (visibleLength(description, cards) > LIMITS.description) throw createError({ statusCode: 400, message: `Описание длиннее ${LIMITS.description} знаков` });
  const missing = [...description.matchAll(TOKEN)].map((m) => m[1]).find((k) => !(k! in cards));
  if (missing) throw createError({ statusCode: 400, message: `Иконка без карточки: ${missing}` });
  if (body.cards) {  // the new cards are kept with the package
    pkg.cards = cards;
    await cf(e).PACKAGES.put(row.package_key, JSON.stringify(pkg), { httpMetadata: { contentType: "application/json" } });
  }
  await run(e, "UPDATE builds SET title = ?, tags = ?, cover = COALESCE(?, cover), tint = COALESCE(?, tint), description = ?, search = ?, updated_at = ? WHERE id = ?",
    title, JSON.stringify(tags), body.cover ?? null, body.tint ?? null, description,
    searchText({ title, mainSkill: row.main_skill, cls: row.cls, asc: row.asc, weapon: row.weapon, tags, skillTags: pkg.skillTags }), now(), id);
  return { ok: true };
});
