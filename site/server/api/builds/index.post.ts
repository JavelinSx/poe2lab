// Publishing from the app (its token): the package checked and kept (publish). What the author edited on the site
// (cover, tint) stays unless the app sends it anew.
import type { BuildPackage } from "~~/shared/package";

export default defineEventHandler(async (e) => {
  const user = await appUser(e);
  const raw = await readRawBody(e, "utf8");
  let pkg: BuildPackage;
  try { pkg = JSON.parse(raw || ""); } catch { throw createError({ statusCode: 400, statusMessage: "Пакет — не JSON" }); }
  return await publish(e, user.id, pkg, raw || "");
});
