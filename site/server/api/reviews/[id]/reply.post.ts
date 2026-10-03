// The build's author answers a review (an empty answer takes it off); the reviewer is notified.
export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const id = getRouterParam(e, "id") || "";
  const { text } = await readBody<{ text: string }>(e);
  const answer = String(text ?? "").trim();
  if (answer.length > 1000) throw createError({ statusCode: 400, statusMessage: "Ответ — до 1000 знаков" });
  const r = await first<{ user_id: string; build_id: string; author_id: string }>(e,
    "SELECT r.user_id, r.build_id, b.author_id FROM reviews r JOIN builds b ON b.id = r.build_id WHERE r.id = ?", id);
  if (!r) throw createError({ statusCode: 404, statusMessage: "Такого отзыва нет" });
  if (r.author_id !== user.id) throw createError({ statusCode: 403, statusMessage: "Отвечать может только автор билда" });
  await run(e, "UPDATE reviews SET reply = ?, reply_at = ? WHERE id = ?", answer || null, answer ? now() : null, id);
  if (answer) await run(e, "INSERT INTO notifications (id, user_id, kind, actor_id, build_id, review_id, created_at) VALUES (?, ?, 'reply', ?, ?, ?, ?)",
    randomId(12), r.user_id, user.id, r.build_id, id, now());
  return { ok: true };
});
