// The one signed in, or null: nick, picture, role, the notifications not read yet (of the kinds they want).
import type { Me } from "~~/shared/api";

export default defineEventHandler(async (e) => {
  const u = await sessionUser(e);
  if (!u) return null;
  const kinds = await wantedKinds(e, u.id);
  const unread = await first<{ n: number }>(e, `SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read_at IS NULL
    AND kind IN (${kinds.map(() => "?").join(", ")})`, u.id, ...kinds);
  return { nick: u.nick, hue: u.hue, avatar: u.avatar, role: u.role, unread: unread?.n ?? 0 } satisfies Me;
});
