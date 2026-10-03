// The signed-in one's notifications, newest first, 30 at a time; only the kinds they want (settings).
import type { Notice } from "~~/shared/api";

export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const before = Number(getQuery(e).before) || now() + 1;
  const kinds = await wantedKinds(e, user.id);
  const rows = await all<{ id: string; kind: Notice["kind"]; actor: string | null; build_id: string | null; title: string | null; stars: number | null;
    text: string; created_at: number; read_at: number | null }>(e,
    `SELECT n.id, n.kind, a.nick AS actor, n.build_id, b.title, r.stars, n.text, n.created_at, n.read_at
     FROM notifications n LEFT JOIN users a ON a.id = n.actor_id LEFT JOIN builds b ON b.id = n.build_id LEFT JOIN reviews r ON r.id = n.review_id
     WHERE n.user_id = ? AND n.created_at < ? AND n.kind IN (${kinds.map(() => "?").join(", ")}) ORDER BY n.created_at DESC LIMIT 30`, user.id, before, ...kinds);
  return rows.map((r): Notice => ({ id: r.id, kind: r.kind, actor: r.actor, build: r.build_id ? { id: r.build_id, title: r.title ?? "" } : null,
    stars: r.stars, text: r.text, at: r.created_at, fresh: !r.read_at }));
});

