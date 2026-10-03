// What the catalog knows on both sides (the pages and the API): classes and their ascendancies, damage types,
// weapons, tags; the search words that are one of them (a plate in the field, a filter in the query).
export type ClassKey = "warrior" | "ranger" | "witch" | "sorc" | "merc" | "monk" | "huntress" | "druid";
export type Dmg = "phys" | "fire" | "cold" | "light" | "chaos";

export const CURRENT_PATCH = "0.5.5";

export const CLASSES: { key: ClassKey; name: string; ascs: string[] }[] = [
  { key: "warrior", name: "Воин", ascs: ["Титан", "Вестник войны", "Кузнец Китавы"] },
  { key: "ranger", name: "Следопыт", ascs: ["Глаз смерти", "Первопроходец"] },
  { key: "witch", name: "Ведьма", ascs: ["Инферналист", "Маг крови", "Лич"] },
  { key: "sorc", name: "Волшебница", ascs: ["Ткач бурь", "Хрономант", "Ученица Варашты"] },
  { key: "merc", name: "Наёмник", ascs: ["Легионер-самоцвет", "Тактик", "Охотник на ведьм"] },
  { key: "monk", name: "Монах", ascs: ["Заклинатель", "Последователь Чаюлы", "Мастер боевых искусств"] },
  { key: "huntress", name: "Охотница", ascs: ["Амазонка", "Ритуалистка", "Духоходица"] },
  { key: "druid", name: "Друид", ascs: ["Шаман", "Оракул"] },
];
export const CLASS_KEYS = CLASSES.map((c) => c.key);

export const DMG: { key: Dmg; name: string; icon: string }[] = [
  { key: "phys", name: "физ", icon: "phys" }, { key: "fire", name: "огонь", icon: "fire" },
  { key: "cold", name: "холод", icon: "cold" }, { key: "light", name: "молния", icon: "bolt" },
  { key: "chaos", name: "хаос", icon: "chaos" },
];
export const DMG_KEYS = DMG.map((d) => d.key);

export const WEAPONS = ["боевой посох", "булава", "лук", "арбалет", "копьё", "посох", "жезл", "скипетр", "талисман"];

export const TAGS: { name: string; icon: string }[] = [
  { name: "старт лиги", icon: "flag" }, { name: "SSF", icon: "lock" }, { name: "бюджет", icon: "coins" },
  { name: "боссы", icon: "skull" }, { name: "маппинг", icon: "map" }, { name: "новичкам", icon: "book" },
];
export const TAG_NAMES = TAGS.map((t) => t.name);

export const className = (k: string) => CLASSES.find((c) => c.key === k)?.name ?? k;
export const norm = (s: string) => s.toLowerCase().replace(/ё/g, "е").trim();

// a word of the search that is a tag, a damage type, a weapon or a class
export function knownWord(w: string): { kind: "tag" | "dmg" | "weapon" | "cls"; key: string; name: string } | null {
  const n = norm(w);
  const tag = TAGS.find((t) => norm(t.name) === n);
  if (tag) return { kind: "tag", key: tag.name, name: tag.name };
  const dmg = DMG.find((d) => norm(d.name) === n);
  if (dmg) return { kind: "dmg", key: dmg.key, name: dmg.name };
  const weapon = WEAPONS.find((x) => norm(x) === n || norm(x).split(" ").pop() === n);
  if (weapon) return { kind: "weapon", key: weapon, name: weapon };
  const cls = CLASSES.find((c) => norm(c.name) === n);
  if (cls) return { kind: "cls", key: cls.key, name: cls.name };
  return null;
}

// what a build is found by: its title, skill, class, ascendancy, weapon, tags and its skill's tags, lower-case
export const searchText = (b: { title: string; mainSkill: string; cls: string; asc: string; weapon: string; tags: string[]; skillTags?: string[] }) =>
  norm([b.title, b.mainSkill, className(b.cls), b.asc, b.weapon, ...b.tags, ...(b.skillTags ?? [])].join(" "));

// a nick: 3-24 letters, digits, _ and -; a few are kept for the site itself
export const NICK = /^[A-Za-zА-Яа-яЁё0-9_-]{3,24}$/;
const RESERVED = ["admin", "administrator", "moderator", "mod", "poe2lab", "support", "ggg", "system"];
export const nickOk = (n: string) => NICK.test(n) && !RESERVED.includes(n.toLowerCase());
