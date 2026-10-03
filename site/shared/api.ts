// What the API answers, typed once for the routes (server/api) and the pages.
import type { ClassKey, Dmg } from "./catalog";
import type { BuildPackage } from "./package";

export interface BuildCard {
  id: string; title: string; cls: ClassKey; asc: string; skill: string; icon?: string; dmg: Dmg; weapon: string;
  dps: number; life: number; es: number; rating: number; reviews: number; author: string; hue: number; avatar?: string;
  patch: string; old?: boolean; tags: string[]; cover: string; opens: number; updated: string; status?: string; views?: number;
}
export interface CatalogData { builds: BuildCard[]; total: number; offset: number; ascendancies: Record<string, number> }
export interface AuthorBrief { nick: string; hue: number; avatar: string | null; classes: ClassKey[]; rating: number; builds: number }
export interface HomeData { classes: Record<string, number>; shelves: { popular: BuildCard[]; start: BuildCard[]; fresh: BuildCard[] }; authors: AuthorBrief[] }

// an author's links: only these sites, always https
export interface UserLink { kind: "twitch" | "youtube"; url: string }
export const LINK_KINDS: Record<UserLink["kind"], { label: string; icon: string; hosts: string[] }> = {
  twitch: { label: "Twitch", icon: "stream", hosts: ["twitch.tv", "www.twitch.tv"] },
  youtube: { label: "YouTube", icon: "play", hosts: ["youtube.com", "www.youtube.com", "youtu.be"] },
};
/** "twitch.tv/x" or "https://www.twitch.tv/x" as a safe https address of that site, or null. */
export function linkUrl(kind: UserLink["kind"], text: string): string | null {
  const t = text.trim();
  if (!t) return null;
  try {
    const u = new URL(/^https?:\/\//i.test(t) ? t : `https://${t}`);
    return LINK_KINDS[kind].hosts.includes(u.hostname.toLowerCase()) && u.pathname.length > 1 ? `https://${u.hostname}${u.pathname}${u.search}`.slice(0, 200) : null;
  } catch { return null; }
}

export type CritKey = "dmg" | "tank" | "budget" | "ease";
export const CRIT: { key: CritKey; icon: string; name: string }[] = [
  { key: "dmg", icon: "sword", name: "Урон" }, { key: "tank", icon: "shield", name: "Живучесть" },
  { key: "budget", icon: "coins", name: "Бюджет" }, { key: "ease", icon: "run", name: "Лёгкость игры" },
];

export interface BuildPageData {
  card: BuildCard;
  page: Pick<BuildPackage, "cards" | "numbers" | "main" | "groups" | "gear" | "gearSummary"> & { description: string; skillTags: string[] };
  reviews: { n: number; avg: number; dist: [number, number][]; crit: Partial<Record<CritKey, number>> };
  author: { nick: string; hue: number; avatar: string | null; builds: number; followers: number; rating: number; links: UserLink[]; following: boolean };
  mine: boolean;
  favorite: boolean;
}

export interface ReviewItem {
  id: string; nick: string; hue: number; avatar: string | null; stars: number; crit: Partial<Record<CritKey, number>>; text: string;
  cls: ClassKey | null; level: number | null; helpful: number; voted?: boolean; own?: boolean; reply: { text: string; at: number } | null; at: number;
  build?: string; // on an author's page: which build it is about
}
export interface ReviewsData {
  items: ReviewItem[];
  mine: { stars: number; crit: Partial<Record<CritKey, number>>; text: string; char_cls: ClassKey | null; char_level: number | null } | null;
}

export interface AuthorPage {
  nick: string; hue: number; avatar: string | null; bio: string; links: UserLink[]; since: number; followers: number; following: boolean;
  builds: BuildCard[]; reviews: ReviewItem[]; reviewsTotal: number;
}
export interface MyBuildCard extends BuildCard { newReviews: number }

export interface Me { nick: string; hue: number; avatar: string | null; role: "user" | "mod" | "owner"; unread: number; fresh?: boolean }
export interface Settings {
  nick: string; bio: string; links: UserLink[]; lang: "ru" | "en"; notify: { reviews: boolean; replies: boolean; follows: boolean };
  discord: boolean; apps: { id: string; name: string; created: number; used: number | null }[];
}
export interface Notice {
  id: string; kind: "review" | "reply" | "follow" | "patch" | "mod"; actor: string | null; build: { id: string; title: string } | null;
  stars: number | null; text: string; at: number; fresh: boolean;
}
