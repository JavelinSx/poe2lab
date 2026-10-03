// The one signed in, or null: nick, picture, role, the notifications not read yet.
export default defineEventHandler(async (e) => {
  const u = await sessionUser(e);
  if (!u) return null;
  const unread = await first<{ n: number }>(e, "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read_at IS NULL", u.id);
  return { nick: u.nick, hue: u.hue, avatar: u.avatar, role: u.role, unread: unread?.n ?? 0 };
});
