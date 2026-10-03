// Keeping a published package: a new version in R2, the catalog's row made or updated - the same build (author + the
// app's key) keeps its address, reviews and numbers.
import type { H3Event } from "h3";
import { checkPackage, type BuildPackage } from "~~/shared/package";
import { searchText } from "~~/shared/catalog";

export async function publish(e: H3Event, userId: string, pkg: BuildPackage, raw?: string) {
  const errs = checkPackage(pkg, raw ?? JSON.stringify(pkg));
  if (errs.length) throw createError({ statusCode: 400, statusMessage: errs[0], data: { errors: errs } });
  const old = await first<{ id: string; version: number }>(e, "SELECT id, version FROM builds WHERE author_id = ? AND app_key = ?", userId, pkg.key);
  const id = old?.id ?? randomId(8);
  const version = (old?.version ?? 0) + 1;
  const key = `builds/${id}/${version}.json`;
  await cf(e).PACKAGES.put(key, JSON.stringify(pkg), { httpMetadata: { contentType: "application/json" } });
  const t = now();
  const search = searchText(pkg);
  if (old) {
    await run(e, `UPDATE builds SET title = ?, cls = ?, asc = ?, main_skill = ?, skill_icon = ?, dmg = ?, weapon = ?, tags = ?, cover = COALESCE(?, cover),
      tint = COALESCE(?, tint), patch = ?, version = ?, package_key = ?, dps = ?, life = ?, es = ?, description = ?, search = ?, status = 'published',
      updated_at = ? WHERE id = ?`, pkg.title, pkg.cls, pkg.asc, pkg.mainSkill, pkg.skillIcon ?? null, pkg.dmg, pkg.weapon, JSON.stringify(pkg.tags),
    pkg.cover ?? null, pkg.tint ?? null, pkg.patch, version, key, pkg.numbers.dps, pkg.numbers.life, pkg.numbers.es, pkg.description, search, t, id);
    if (version > 2) await cf(e).PACKAGES.delete(`builds/${id}/${version - 2}.json`);  // two versions are kept
  } else {
    await run(e, `INSERT INTO builds (id, author_id, app_key, title, cls, asc, main_skill, skill_icon, dmg, weapon, tags, cover, tint, patch, version,
      package_key, dps, life, es, description, search, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    id, userId, pkg.key, pkg.title, pkg.cls, pkg.asc, pkg.mainSkill, pkg.skillIcon ?? null, pkg.dmg, pkg.weapon, JSON.stringify(pkg.tags),
    pkg.cover ?? null, pkg.tint ?? null, pkg.patch, version, key, pkg.numbers.dps, pkg.numbers.life, pkg.numbers.es, pkg.description, search, t, t);
  }
  return { id, version, url: `/b/${id}`, updated: Boolean(old) };
}
