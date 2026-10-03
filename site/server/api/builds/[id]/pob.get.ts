// The build's PoB code, asked for when the reader copies it (it is too big to come with the page).
import type { BuildPackage } from "~~/shared/package";

export default defineEventHandler(async (e) => {
  const id = getRouterParam(e, "id") || "";
  const row = await first<{ package_key: string; status: string; author_id: string }>(e, "SELECT package_key, status, author_id FROM builds WHERE id = ?", id);
  const me = row?.status === "hidden" ? await sessionUser(e) : null;
  if (!row || row.status === "removed" || (row.status === "hidden" && me?.id !== row.author_id)) throw createError({ statusCode: 404, message: "Такого билда нет" });
  const obj = await cf(e).PACKAGES.get(row.package_key);
  if (!obj) throw createError({ statusCode: 500, message: "Пакет билда потерян" });
  return { pob: (JSON.parse(await obj.text()) as BuildPackage).pob };
});
