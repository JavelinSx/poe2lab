// Authors' public profiles until the API (/api/authors/:nick): about, links, numbers, recent reviews on their builds.
import type { Review } from "./page";

export interface AuthorProfile {
  nick: string; hue: number; bio: string; since: string; followers: number; top?: boolean;
  links: { label: string; icon: string; href: string }[];
  reviews: (Review & { build: string })[]; reviewsTotal: number;
}

export const PROFILES: Record<string, AuthorProfile> = {
  MapMama: {
    nick: "MapMama", hue: 330, top: true, since: "с марта 2026", followers: 3100,
    bio: "Собираю бюджетные билды для первой недели лиги и для тех, кто только начал. Всё проверяю на своём персонаже до 90+ уровня.",
    links: [{ label: "Twitch", icon: "stream", href: "#twitch" }, { label: "YouTube", icon: "play", href: "#youtube" }],
    reviewsTotal: 214,
    reviews: [
      { build: "b8", nick: "Kotofey", hue: 140, cls: "sorc", clsName: "Волшебница", level: 81, stars: 5, when: "вчера", helpful: 41,
        text: "Первый раз дошёл до карт без гайдов на ютубе. Описание короткое, но всё по делу, а прокачку я смотрел уже в приложении.",
        reply: { text: "Ура! Дальше смотри «Хрономанта» — там будет удобнее на боссах.", when: "вчера" } },
      { build: "b3", nick: "Vlad_SSF", hue: 260, cls: "witch", clsName: "Ведьма", level: 74, stars: 4, when: "3 дня назад", helpful: 12,
        text: "В SSF играется хорошо, но на боссах миньоны тают. Помогло поднять уровень камня скелетов раньше, чем в описании." },
    ],
  },
};

// an author without a profile of their own in the mock: one made from the builds' cards
export function profileOf(nick: string, hue = 210): AuthorProfile {
  return PROFILES[nick] ?? { nick, hue, bio: "", since: "с 2026", followers: 0, links: [], reviews: [], reviewsTotal: 0 };
}
