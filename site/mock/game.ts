// A few of the game's things for the description editor's search until the API (/api/lookup): what a token can be,
// with its card and tags (the real list is the app's search index, poe2lab/author.py).
import type { Card } from "./page";

export interface GameThing { key: string; kind: "skill" | "support" | "unique" | "pass" | "term"; card: Card; tags: string[] }

const t = (key: string, kind: GameThing["kind"], card: Card, tags: string[]): GameThing => ({ key, kind, card, tags });
export const THINGS: GameThing[] = [
  t("skill:ice-strike", "skill", { kind: "skill", name: "Ледяной удар", sub: "активный камень", img: "ice-strike", game: true }, ["атака", "удар", "боевой посох", "холод", "область"]),
  t("skill:tempest-flurry", "skill", { kind: "skill", name: "Шквал бури", sub: "активный камень", img: "tempest-flurry", game: true }, ["атака", "удар", "боевой посох", "молния"]),
  t("skill:flicker", "skill", { kind: "skill", name: "Внезапный удар", sub: "активный камень", img: "flicker", game: true }, ["атака", "удар", "боевой посох", "ближний бой"]),
  t("skill:shattering-palm", "skill", { kind: "skill", name: "Раскалывающая длань", sub: "активный камень", img: "shattering-palm", game: true }, ["атака", "удар", "боевой посох", "холод"]),
  t("skill:staff-strike", "skill", { kind: "skill", name: "Удар посохом", sub: "активный камень", img: "staff-strike", game: true }, ["атака", "удар", "боевой посох"]),
  t("skill:glacial-cascade", "skill", { kind: "skill", name: "Ледяной каскад", sub: "активный камень", img: "glacial-cascade", game: true }, ["атака", "область", "холод"]),
  t("skill:charged-staff", "skill", { kind: "skill", name: "Заряженный посох", sub: "активный камень", img: "charged-staff", game: true }, ["бафф", "молния", "боевой посох"]),
  t("skill:freezing-mark", "skill", { kind: "skill", name: "Метка заморозки", sub: "активный камень", img: "freezing-mark", game: true }, ["метка", "холод"]),
  t("skill:tempest-bell", "skill", { kind: "skill", name: "Колокол бури", sub: "активный камень", ph: "light", game: true }, ["атака", "могучий удар", "молния"]),
  t("support:cold-mastery", "support", { kind: "support", name: "Мастерство холода", sub: "камень поддержки", img: "cold-mastery", game: true }, ["холод", "поддержка"]),
  t("support:culling", "support", { kind: "support", name: "Добивание II", sub: "камень поддержки", img: "culling", game: true }, ["атака", "поддержка"]),
  t("support:ambush", "support", { kind: "support", name: "Удар врасплох", sub: "камень поддержки", img: "ambush", game: true }, ["атака", "критический удар", "поддержка"]),
  t("unique:hand-of-chayula", "unique", { kind: "unique", name: "Рука Чаюлы", sub: "Перчатки · ур. 65", img: "i-gloves",
    mods: ["+72 к максимуму энергетического щита", "Критические удары замораживают врагов", "12% повышение скорости атаки"], game: true }, ["перчатки", "энергощит", "холод"]),
  t("pass:precise-strike", "pass", { kind: "pass", name: "Точный удар", sub: "ключевой узел дерева", img: "p-crit",
    mods: ["+20% к шансу критического удара", "+15% к урону критических ударов"], game: true }, ["значимое", "критический удар"]),
  t("term:freeze", "term", { kind: "term", name: "Заморозка", desc: "Замороженный враг не двигается и не атакует, пока заморозка не спадёт." }, ["холод", "контроль"]),
  t("term:es", "term", { kind: "term", name: "Энергетический щит", desc: "Запас поверх здоровья: принимает урон первым и восстанавливается, если какое-то время не получать урон." }, ["защита", "энергощит"]),
  t("term:crit", "term", { kind: "term", name: "Критический удар", desc: "Удар с повышенным уроном; шанс зависит от оружия и модификаторов." }, ["критический удар"]),
];

export const KIND_LABEL: Record<GameThing["kind"], string> = { skill: "скилл", support: "поддержка", unique: "уник", pass: "пассивка", term: "термин" };
