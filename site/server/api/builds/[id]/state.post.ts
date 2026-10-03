// The author takes the build off the site or gives it back; deleting is for good (its packages go too).
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  const { state } = await readBody<{ state: "published" | "hidden" | "removed" }>(e);
  if (!["published", "hidden", "removed"].includes(state)) throw createError({ statusCode: 400, message: "Неизвестное состояние" });
  const row = await first<{ author_id: string; version: number }>(e, "SELECT author_id, version FROM builds WHERE id = ? AND status != 'removed'", id);
  if (!row) throw createError({ statusCode: 404, message: "Такого билда нет" });
  if (row.author_id !== user.id && user.role === "user") throw createError({ statusCode: 403, message: "Это не твой билд" });
  if (state === "removed") {
    await cf(e).PACKAGES.delete([`builds/${id}/${row.version}.json`, `builds/${id}/${row.version - 1}.json`]);
    await run(e, "DELETE FROM builds WHERE id = ?", id);
    return { ok: true, removed: true };
  }
  await run(e, "UPDATE builds SET status = ?, updated_at = ? WHERE id = ?", state, now(), id);
  return { ok: true, state };
});
