// What the settings page shows: nick, about, links, language, which notifications, how one signs in, the apps.
import type { Settings } from "~~/shared/api";

export default defineEventHandler(async (e) => {
  const user = await requireUser(e);
  const [u, apps] = await Promise.all([
    first<{ nick: string; bio: string; links: string; lang: string; notify: string; discord_id: string | null }>(e,
      "SELECT nick, bio, links, lang, notify, discord_id FROM users WHERE id = ?", user.id),
    all<{ id: string; name: string; created_at: number; last_used_at: number | null }>(e,
      "SELECT id, name, created_at, last_used_at FROM app_tokens WHERE user_id = ? ORDER BY created_at DESC", user.id),
  ]);
  return {
    nick: u!.nick, bio: u!.bio, links: parseJson(u!.links, []), lang: u!.lang === "en" ? "en" : "ru",
    notify: { reviews: true, replies: true, follows: true, ...parseJson(u!.notify, {}) }, discord: Boolean(u!.discord_id),
    apps: apps.map((a) => ({ id: a.id, name: a.name, created: a.created_at, used: a.last_used_at })),
  } satisfies Settings;
});
