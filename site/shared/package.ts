// The package the app publishes (docs/SITE.md): what the build's page shows - computed by PoB on the author's computer,
// the site never recomputes it - and its checks (sizes, kinds, the author's text with its pieces).
import { CLASS_KEYS, DMG_KEYS, TAG_NAMES, type ClassKey, type Dmg } from "./catalog";

export type CardKind = "skill" | "support" | "unique" | "rare" | "magic" | "pass" | "term" | "rune";
export interface Card {
  kind: CardKind; name: string; sub?: string; img?: string; ph?: Dmg; tags?: string[];
  kv?: [string, string][]; mods?: string[]; runes?: { img: string; text: string }[]; desc?: string; game?: boolean;
}
export interface Gem { name: string; img?: string; ph?: Dmg; card?: Card }
export interface Link { name: string; img?: string; ph?: Dmg; dmg?: Dmg; dmgName?: string; badge?: string; supports: Gem[] }
export interface GearItem { slot: string; pos: string; label: string; card?: Card; img?: string; rarity?: "rare" | "unique" | "magic" | "normal"; runes?: string[]; tip?: "below" | "left" | "right" }
export type Resist = number | "imm";

export interface BuildPackage {
  v: 1;
  app: string;                // "poe2lab 0.9"
  key: string;                // the build's key in the app: publishing it again updates the same page
  patch: string;
  title: string;
  tags: string[];
  cls: ClassKey; asc: string; mainSkill: string; skillIcon?: string; skillTags?: string[]; dmg: Dmg; weapon: string;
  cover?: string; tint?: Dmg;
  numbers: {
    dps: number; dpsNote?: string; life: number; es: number; poolNote?: string;
    res: { fire: Resist; cold: Resist; light: Resist; chaos: Resist };
    defence: { value: number; kind: string; extra?: string };
  };
  description: string;        // with tokens [[kind:key]], each key in cards
  cards: Record<string, Card>;
  main: { name: string; img?: string; level?: string; dmg?: Dmg; dmgName?: string; tags?: string; supports: Gem[]; note?: string };
  groups: { title: string; links: Link[] }[];
  gear: GearItem[];
  gearSummary?: string;
  pob: string;                // the PoB code
}

export const LIMITS = { bytes: 300_000, title: 60, tags: 5, description: 1500, cards: 400, groups: 12, links: 40, supports: 8, gear: 24, pob: 200_000, text: 600 };
export const TOKEN = /\[\[([a-z]+:[^[\]\n]{1,200})\]\]/g;

// what the reader sees counts: a piece by its name
export const visibleLength = (text: string, cards: Record<string, Card>) => text.replace(TOKEN, (_, k: string) => cards[k]?.name ?? "").length;

const CARD_KINDS: CardKind[] = ["skill", "support", "unique", "rare", "magic", "pass", "term", "rune"];
const isStr = (v: unknown, max: number) => typeof v === "string" && v.length <= max;
const isNum = (v: unknown) => typeof v === "number" && Number.isFinite(v);
// a picture's name or the game CDN's address
const isImg = (v: unknown) => v === undefined || (typeof v === "string" && v.length <= 300 && (/^[\w-]+$/.test(v) || /^https:\/\/web\.poecdn\.com\//.test(v)));

/** A card is good to keep: its key, kind, name, picture, lines. */
export function cardOk(k: string, c: Card | undefined): boolean {
  return /^[a-z]+:[^[\]\n]{1,200}$/.test(k) && !!c && CARD_KINDS.includes(c.kind) && isStr(c.name, 120) && isImg(c.img)
    && (c.sub === undefined || isStr(c.sub, 120)) && (c.desc === undefined || isStr(c.desc, LIMITS.text))
    && (!c.mods || (Array.isArray(c.mods) && c.mods.length <= 30 && c.mods.every((m) => isStr(m, LIMITS.text))))
    && (!c.tags || (Array.isArray(c.tags) && c.tags.length <= 12 && c.tags.every((t) => isStr(t, 40))));
}

/** The package's problems in words, none when it is good to keep. */
export function checkPackage(p: unknown, raw?: string): string[] {
  const errs: string[] = [];
  const fail = (m: string) => { errs.push(m); return errs; };
  if (raw !== undefined && raw.length > LIMITS.bytes) return fail(`пакет больше ${LIMITS.bytes / 1000} КБ`);
  if (!p || typeof p !== "object") return fail("пакет — не объект");
  const b = p as Partial<BuildPackage>;
  if (b.v !== 1) errs.push("неизвестная версия пакета");
  if (!isStr(b.app, 60) || !isStr(b.key, 80) || !b.key) errs.push("нет ключа билда или версии приложения");
  if (!isStr(b.patch, 12) || !/^\d+\.\d+(\.\d+)?$/.test(b.patch!)) errs.push("патч — вида 0.5.5");
  if (!isStr(b.title, LIMITS.title) || !b.title!.trim()) errs.push(`название — от 1 до ${LIMITS.title} знаков`);
  if (!Array.isArray(b.tags) || b.tags.length > LIMITS.tags || b.tags.some((t) => !TAG_NAMES.includes(t))) errs.push(`теги — до ${LIMITS.tags} из списка сайта`);
  if (!CLASS_KEYS.includes(b.cls as ClassKey)) errs.push("неизвестный класс");
  if (!DMG_KEYS.includes(b.dmg as Dmg) || (b.tint !== undefined && !DMG_KEYS.includes(b.tint))) errs.push("неизвестный тип урона");
  for (const [k, max] of [["asc", 40], ["mainSkill", 60], ["weapon", 40]] as const) if (!isStr(b[k], max)) errs.push(`поле ${k} — строка до ${max} знаков`);
  if (!isImg(b.skillIcon) || !isImg(b.cover)) errs.push("картинка — имя или адрес CDN игры");
  const n = b.numbers;
  if (!n || ![n.dps, n.life, n.es, n.defence?.value].every(isNum) || !n.res || !n.defence || !isStr(n.defence.kind, 40)
      || !(["fire", "cold", "light", "chaos"] as const).every((k) => n.res[k] === "imm" || isNum(n.res[k]))) errs.push("цифры билда неполные");
  const cards = b.cards;
  if (!cards || typeof cards !== "object" || Object.keys(cards).length > LIMITS.cards) errs.push(`карточек — до ${LIMITS.cards}`);
  else {
    const bad = Object.entries(cards).find(([k, c]) => !cardOk(k, c));
    if (bad) errs.push(`карточка ${bad[0].slice(0, 40)} неверная`);
  }
  if (!isStr(b.description, 20_000)) errs.push("описание — строка");
  else if (cards && typeof cards === "object") {
    if (visibleLength(b.description!, cards) > LIMITS.description) errs.push(`описание длиннее ${LIMITS.description} знаков`);
    const missing = [...b.description!.matchAll(TOKEN)].map((m) => m[1]).filter((k) => !(k in cards));
    if (missing.length) errs.push(`в описании иконка без карточки: ${missing[0]}`);
  }
  if (!b.main || !isStr(b.main.name, 80) || !Array.isArray(b.main.supports) || b.main.supports.length > LIMITS.supports) errs.push("главная связка неверная");
  if (!Array.isArray(b.groups) || b.groups.length > LIMITS.groups || b.groups.reduce((s, g) => s + (Array.isArray(g?.links) ? g.links.length : 99), 0) > LIMITS.links) errs.push("связок слишком много");
  if (!Array.isArray(b.gear) || b.gear.length > LIMITS.gear || b.gear.some((g) => !g || !isStr(g.pos, 20) || !isStr(g.slot, 40) || !isImg(g.img))) errs.push("снаряжение неверное");
  if (!isStr(b.pob, LIMITS.pob) || !b.pob) errs.push("нет кода PoB");
  return errs;
}
