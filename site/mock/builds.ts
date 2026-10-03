// Mock builds for the pages until the API is there (the design's examples: design/site/src/_parts/builds.json).
// The shape is what /api/builds will answer with (docs/SITE.md): the card's fields, and for one build its page.
export type ClassKey = "warrior" | "ranger" | "witch" | "sorc" | "merc" | "monk" | "huntress" | "druid";
export type Dmg = "phys" | "fire" | "cold" | "light" | "chaos";

export interface BuildCard {
  id: string;
  title: string;
  cls: ClassKey;
  asc: string;
  skill: string;
  icon?: string; // the main skill's picture (public/game/<icon>.png); without one, the damage type's glyph
  dmg: Dmg;
  weapon: string;
  dps: number;
  life: number;
  es: number;
  rating: number;
  reviews: number;
  author: string;
  hue: number; // the author's avatar colour until there is a Discord picture
  patch: string;
  old?: boolean; // made for an earlier patch
  tags: string[];
  cover: string;
  opens: number; // how many opened it in poe2lab this week
  updated: string; // ISO date
}

export const CURRENT_PATCH = "0.5.5";

export const BUILDS: BuildCard[] = [
  { id: "b1", title: "Ледяной удар + Колокол бури — старт лиги", cls: "monk", asc: "Заклинатель", skill: "Ледяной удар", icon: "ice-strike", dmg: "cold", weapon: "боевой посох", dps: 312400, life: 1, es: 3640, rating: 4.6, reviews: 38, author: "Inverno", hue: 205, patch: "0.5.5", tags: ["старт лиги", "бюджет", "маппинг"], cover: "i-staff", opens: 2140, updated: "2026-09-12" },
  { id: "b2", title: "Взрывные гранаты наёмника", cls: "merc", asc: "Тактик", skill: "Взрывная граната", dmg: "fire", weapon: "арбалет", dps: 248900, life: 2310, es: 1120, rating: 4.4, reviews: 21, author: "Granatnik", hue: 22, patch: "0.5.5", tags: ["маппинг", "боссы"], cover: "i-body2", opens: 980, updated: "2026-09-20" },
  { id: "b3", title: "Армия миньонов ведьмы", cls: "witch", asc: "Инферналист", skill: "Скелеты-воины", icon: "skeleton", dmg: "phys", weapon: "скипетр", dps: 186500, life: 3050, es: 0, rating: 4.8, reviews: 64, author: "NecroNastya", hue: 290, patch: "0.5.5", tags: ["новичкам", "старт лиги", "SSF"], cover: "i-amulet2", opens: 3010, updated: "2026-09-18" },
  { id: "b4", title: "Яростный удар титана", cls: "warrior", asc: "Титан", skill: "Яростный удар", dmg: "phys", weapon: "булава", dps: 404200, life: 5870, es: 0, rating: 4.2, reviews: 17, author: "KitavaSmith", hue: 12, patch: "0.5.5", tags: ["боссы", "бюджет"], cover: "i-helmet", opens: 640, updated: "2026-09-29" },
  { id: "b5", title: "Стрела молнии через весь экран", cls: "ranger", asc: "Первопроходец", skill: "Стрела молнии", dmg: "light", weapon: "лук", dps: 356700, life: 3400, es: 900, rating: 4.5, reviews: 29, author: "Strelok", hue: 120, patch: "0.5.5", tags: ["маппинг", "SSF"], cover: "i-boots", opens: 1220, updated: "2026-09-15" },
  { id: "b6", title: "Похищение сущности: хаос и лич", cls: "witch", asc: "Лич", skill: "Похищение сущности", dmg: "chaos", weapon: "жезл", dps: 221300, life: 2880, es: 1600, rating: 4.1, reviews: 12, author: "VoidCaller", hue: 280, patch: "0.4.3", old: true, tags: ["боссы"], cover: "i-ring3", opens: 210, updated: "2026-06-02" },
  { id: "b7", title: "Шквал бури: молнии с посоха", cls: "monk", asc: "Последователь Чаюлы", skill: "Шквал бури", icon: "tempest-flurry", dmg: "light", weapon: "боевой посох", dps: 289000, life: 1, es: 4210, rating: 4.7, reviews: 45, author: "frostmonk", hue: 200, patch: "0.5.5", tags: ["маппинг", "старт лиги"], cover: "i-staff2", opens: 2560, updated: "2026-09-26" },
  { id: "b8", title: "Ледяной каскад для первой лиги", cls: "sorc", asc: "Хрономант", skill: "Ледяной каскад", icon: "glacial-cascade", dmg: "cold", weapon: "посох", dps: 194300, life: 3200, es: 1800, rating: 4.9, reviews: 102, author: "MapMama", hue: 330, patch: "0.5.5", tags: ["новичкам", "бюджет", "старт лиги"], cover: "i-body3", opens: 4120, updated: "2026-09-10" },
  { id: "b9", title: "Раскалывающая длань: заморозка и осколки", cls: "monk", asc: "Заклинатель", skill: "Раскалывающая длань", icon: "shattering-palm", dmg: "cold", weapon: "боевой посох", dps: 268800, life: 1, es: 3980, rating: 4.3, reviews: 9, author: "IceIsNice", hue: 185, patch: "0.5.5", tags: ["боссы"], cover: "i-gloves", opens: 430, updated: "2026-10-01" },
  { id: "b10", title: "Внезапный удар: телепорт и криты", cls: "monk", asc: "Заклинатель", skill: "Внезапный удар", icon: "flicker", dmg: "light", weapon: "боевой посох", dps: 382100, life: 1, es: 3620, rating: 4.0, reviews: 7, author: "Shadowstep", hue: 250, patch: "0.5.5", tags: ["боссы", "маппинг"], cover: "i-ring", opens: 390, updated: "2026-10-02" },
  { id: "b11", title: "Копьё молнии амазонки", cls: "huntress", asc: "Амазонка", skill: "Копьё молнии", dmg: "light", weapon: "копьё", dps: 301500, life: 3650, es: 0, rating: 4.6, reviews: 31, author: "SpearQueen", hue: 340, patch: "0.5.5", tags: ["маппинг"], cover: "i-body", opens: 1880, updated: "2026-09-22" },
  { id: "b12", title: "Вулкан и рёв: друид-шаман", cls: "druid", asc: "Шаман", skill: "Вулкан", dmg: "fire", weapon: "талисман", dps: 233400, life: 4100, es: 0, rating: 4.4, reviews: 15, author: "OakAndAsh", hue: 95, patch: "0.5.5", tags: ["SSF", "боссы"], cover: "i-belt", opens: 760, updated: "2026-09-24" },
];

export const CLASSES: { key: ClassKey; name: string; ascs: string[] }[] = [
  { key: "warrior", name: "Воин", ascs: ["Титан", "Вестник войны", "Кузнец Китавы"] },
  { key: "ranger", name: "Следопыт", ascs: ["Глаз смерти", "Первопроходец"] },
  { key: "witch", name: "Ведьма", ascs: ["Инферналист", "Маг крови", "Лич"] },
  { key: "sorc", name: "Волшебница", ascs: ["Ткач бурь", "Хрономант"] },
  { key: "merc", name: "Наёмник", ascs: ["Легионер-самоцвет", "Тактик", "Охотник на ведьм"] },
  { key: "monk", name: "Монах", ascs: ["Заклинатель", "Последователь Чаюлы"] },
  { key: "huntress", name: "Охотница", ascs: ["Амазонка", "Ритуалистка"] },
  { key: "druid", name: "Друид", ascs: ["Шаман", "Оракул"] },
];

export const DMG: { key: Dmg; name: string; icon: string }[] = [
  { key: "phys", name: "физ", icon: "phys" }, { key: "fire", name: "огонь", icon: "fire" },
  { key: "cold", name: "холод", icon: "cold" }, { key: "light", name: "молния", icon: "bolt" },
  { key: "chaos", name: "хаос", icon: "chaos" },
];

export const WEAPONS = ["боевой посох", "булава", "лук", "арбалет", "копьё", "посох", "жезл", "скипетр", "талисман"];

export const TAGS: { name: string; icon: string }[] = [
  { name: "старт лиги", icon: "flag" }, { name: "SSF", icon: "lock" }, { name: "бюджет", icon: "coins" },
  { name: "боссы", icon: "skull" }, { name: "маппинг", icon: "map" }, { name: "новичкам", icon: "book" },
];

export const AUTHORS = [
  { nick: "MapMama", hue: 330, classes: ["sorc", "witch"], rating: 4.8, builds: 6 },
  { nick: "NecroNastya", hue: 290, classes: ["witch"], rating: 4.7, builds: 4 },
  { nick: "frostmonk", hue: 200, classes: ["monk", "sorc"], rating: 4.6, builds: 9, following: true },
  { nick: "SpearQueen", hue: 340, classes: ["huntress"], rating: 4.6, builds: 3 },
  { nick: "Strelok", hue: 120, classes: ["ranger", "merc"], rating: 4.5, builds: 5 },
  { nick: "KitavaSmith", hue: 12, classes: ["warrior"], rating: 4.3, builds: 7 },
] as const;

export const className = (k: ClassKey) => CLASSES.find((c) => c.key === k)?.name ?? k;
