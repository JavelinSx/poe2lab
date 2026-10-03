// Which notifications a person sees: the kinds they want in the settings; the site's own (patch, moderation) always.
import type { H3Event } from "h3";
import type { Settings } from "~~/shared/api";

const KIND_OF: Record<string, keyof Settings["notify"] | null> = { review: "reviews", reply: "replies", follow: "follows", patch: null, mod: null };

export async function wantedKinds(e: H3Event, userId: string) {
  const u = await first<{ notify: string }>(e, "SELECT notify FROM users WHERE id = ?", userId);
  const want = parseJson<Partial<Settings["notify"]>>(u?.notify, {});
  return Object.entries(KIND_OF).filter(([, k]) => !k || want[k] !== false).map(([kind]) => kind);
}
