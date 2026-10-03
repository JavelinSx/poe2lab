// One build's page as the API will give it: what the app published (numbers, skills, gear, the author's text with
// its pieces and their cards) and the site's own (reviews). The design's example (design/site/src/Build.dc.html).
import type { Dmg } from "./builds";

export type CardKind = "skill" | "support" | "unique" | "rare" | "magic" | "pass" | "term" | "rune";
export interface Card {
  kind: CardKind;
  name: string;
  sub?: string; // "камень поддержки", "Боевой посох · ур. 72"
  img?: string; // public/game/<img>.png
  ph?: Dmg; // no picture yet: the damage type's glyph
  tags?: string[];
  kv?: [string, string][]; // "Физический урон: 98–164"
  mods?: string[];
  runes?: { img: string; text: string }[];
  desc?: string;
  game?: boolean; // the text is the game's own data
}

export interface GearItem { slot: string; pos: string; label: string; card?: Card; img?: string; rarity?: "rare" | "unique" | "magic"; runes?: string[]; tip?: "below" | "left" | "right" }
export interface Gem { name: string; img?: string; ph?: Dmg; card?: Card }
export interface Link { name: string; img?: string; ph?: Dmg; dmg?: Dmg; dmgName?: string; badge?: string; supports: Gem[] }
export interface Review {
  nick: string; hue: number; cls: string; clsName: string; level: number; stars: number; when: string; text: string;
  crit?: [string, number][]; helpful: number; voted?: boolean; reply?: { text: string; when: string };
}

export interface BuildPage {
  id: string;
  description: string; // with tokens [[kind:key]] - each key in cards
  cards: Record<string, Card>;
  numbers: {
    dps: number; dpsNote: string; life: number; es: number; poolNote: string;
    res: { fire: number | "imm"; cold: number | "imm"; light: number | "imm"; chaos: number | "imm" };
    defence: { value: number; kind: string; extra?: string };
  };
  main: { name: string; img: string; level: string; dmg: Dmg; dmgName: string; tags: string; supports: Gem[]; note?: string };
  groups: { title: string; links: Link[] }[];
  gear: GearItem[];
  gearSummary: string;
  links: { label: string; icon: string; href: string }[];
  reviews: {
    avg: number; n: number; dist: [number, number][]; crit: [string, string, number][]; items: Review[];
  };
  followers: number;
  views: number;
}

const game = true;
export const PAGES: Record<string, BuildPage> = {
  b1: {
    id: "b1",
    description: "Билд для первых дней лиги: бьём [[skill:ice-strike]] с боевого посоха, а [[skill:tempest-bell]] добивает толпу вокруг. Всё держится на [[term:crit]] и [[term:freeze]]: замороженные враги не отвечают.\n" +
      "Весь запас — в [[term:es]], здоровья одна единица. До 40 уровня играй через [[skill:glacial-cascade]], потом переходи на удар. Главная вещь — [[unique:hand-of-chayula]], но первые карты проходятся и без неё.\n" +
      "В дереве сначала бери [[pass:precise-strike]] и узлы энергощита. Сопротивление огню пока не в капе — закрой его кольцом или руной.",
    cards: {
      "skill:ice-strike": { kind: "skill", name: "Ледяной удар", sub: "активный камень", img: "ice-strike", tags: ["атака", "удар", "область", "холод", "боевой посох"],
        mods: ["Бьёт сериями по три: третий удар выпускает ледяные волны по области"], game },
      "skill:tempest-bell": { kind: "skill", name: "Колокол бури", sub: "активный камень", ph: "light", tags: ["атака", "могучий удар", "молния"],
        mods: ["Ставит колокол; удары по нему расходятся волнами по области"], game },
      "skill:glacial-cascade": { kind: "skill", name: "Ледяной каскад", sub: "активный камень", img: "glacial-cascade", tags: ["атака", "область", "холод"], game },
      "term:crit": { kind: "term", name: "Критический удар", desc: "Удар с повышенным уроном; шанс зависит от оружия и модификаторов." },
      "term:freeze": { kind: "term", name: "Заморозка", desc: "Замороженный враг не двигается и не атакует, пока заморозка не спадёт." },
      "term:es": { kind: "term", name: "Энергетический щит", desc: "Запас поверх здоровья: принимает урон первым и восстанавливается, если какое-то время не получать урон." },
      "unique:hand-of-chayula": { kind: "unique", name: "Рука Чаюлы", sub: "Перчатки · ур. 65", img: "i-gloves",
        mods: ["+72 к максимуму энергетического щита", "Критические удары замораживают врагов", "12% повышение скорости атаки"], desc: "«Тьма помнит каждое касание».", game },
      "pass:precise-strike": { kind: "pass", name: "Точный удар", sub: "ключевой узел дерева", img: "p-crit",
        mods: ["+20% к шансу критического удара", "+15% к урону критических ударов"], desc: "Узел у центра дерева Монаха, 6 очков от старта.", game },
      "support:culling": { kind: "support", name: "Добивание II", sub: "камень поддержки", img: "culling", game },
    },
    numbers: {
      dps: 312400, dpsNote: "Ледяной удар, одна цель", life: 1, es: 3640, poolNote: "весь запас — в энергощите",
      res: { fire: 66, cold: 75, light: 75, chaos: "imm" }, defence: { value: 12035, kind: "уклонение", extra: "отклонение 24%" },
    },
    main: {
      name: "Ледяной удар", img: "ice-strike", level: "ур. 20 · кач. 20%", dmg: "cold", dmgName: "холод", tags: "атака · удар · боевой посох",
      supports: [
        { name: "Удар врасплох", img: "ambush", card: { kind: "support", name: "Удар врасплох", sub: "камень поддержки", tags: ["атака", "критический удар"],
          mods: ["Поддерживаемые атаки получают +25% к шансу критического удара против врагов с полным здоровьем"], kv: [["Множитель стоимости", "110%"]], game } },
        { name: "Точечные критические удары", img: "pinpoint" }, { name: "Мастерство холода", img: "cold-mastery" },
        { name: "Стихийное оружие II", img: "elem-armament" }, { name: "Разъярение II", img: "rage" },
      ],
      note: "бей сериями по три — третий удар выпускает ледяные волны по области. На боссах меняй «Мастерство холода» на [[support:culling]].",
    },
    groups: [
      { title: "Урон", links: [
        { name: "Колокол бури", ph: "light", dmg: "light", dmgName: "молния", supports: [{ name: "Ускорение перезарядки II", img: "cooldown" }, { name: "Средоточие", img: "concentrated" }, { name: "Продление II", img: "prolonged" }] },
        { name: "Ледяной каскад", img: "glacial-cascade", dmg: "cold", dmgName: "холод", badge: "до 40 ур.", supports: [{ name: "Эффективность II", img: "efficiency" }, { name: "Ослепление II", img: "blind" }] },
        { name: "Метка заморозки", img: "freezing-mark", dmg: "cold", dmgName: "холод", supports: [{ name: "Увечье", img: "maim" }] },
      ] },
      { title: "Дух и баффы", links: [
        { name: "Вечная ярость", img: "eternal-rage", badge: "дух 60", supports: [] },
        { name: "Слияние стихий", img: "conflux", badge: "дух 56", supports: [] },
        { name: "Сотворение чар при критическом попадании", img: "cast-on-crit", supports: [{ name: "Выход стихии", img: "elem-expression" }] },
      ] },
      { title: "Передвижение", links: [
        { name: "Вихревой налёт", img: "whirling", supports: [{ name: "Быстрые атаки II", img: "rapid-attacks" }, { name: "Удар с разбега", img: "running-assault" }] },
        { name: "Танцующий с ветром", img: "wind-dancer", supports: [] },
      ] },
    ],
    gear: [
      { slot: "Оружие", pos: "weapon", label: "Боевой посох", img: "i-staff", rarity: "rare", runes: ["rune-cold-p", "rune-cold-p"], tip: "right",
        card: { kind: "rare", name: "Гроза Стужи", sub: "Боевой посох · ур. 72", kv: [["Физический урон", "98–164"], ["Шанс крит. удара", "11,5%"], ["Атак в секунду", "1,40"]],
          mods: ["Добавляет 41–68 урона от холода", "+31% к урону критических ударов", "+2 к уровню камней ближнего боя", "14% повышение скорости атаки"],
          runes: [{ img: "rune-cold-p", text: "Руна холода ×2: +18% урона от холода" }] } },
      { slot: "Вторая рука", pos: "offhand", label: "двуручное оружие" },
      { slot: "Шлем", pos: "helmet", label: "Шлем", img: "i-helmet", rarity: "rare", runes: ["rune-desert"],
        card: { kind: "rare", name: "Венец Тишины", sub: "Шлем · ур. 68", kv: [["Уклонение", "412"], ["Энергощит", "138"]],
          mods: ["+64 к максимуму энергетического щита", "+38% к сопротивлению холоду", "+26% к сопротивлению молнии"], runes: [{ img: "rune-desert", text: "Руна пустыни: +12% к сопротивлению огню" }] } },
      { slot: "Амулет", pos: "amulet", label: "Амулет", img: "i-amulet", rarity: "unique", tip: "left",
        card: { kind: "unique", name: "Удушающее веление", sub: "Амулет · ур. 58", mods: ["+30 к духу", "+18% к шансу критического удара", "Враги рядом с тобой замедлены на 10%"], desc: "«Воля сильнее — дыхание тише»." } },
      { slot: "Нательная броня", pos: "body", label: "Нательная броня", img: "i-body", rarity: "rare", runes: ["rune-storm-g", "rune-storm-g"],
        card: { kind: "rare", name: "Покров Сумрака", sub: "Дублёный плащ · ур. 81", kv: [["Уклонение", "1 204"], ["Энергощит", "356"]],
          mods: ["+189 к уклонению / +53 к максимуму энергетического щита", "99% повышение уклонения и энергетического щита", "+40% к сопротивлению холоду", "+31% к сопротивлению молнии"],
          runes: [{ img: "rune-storm-g", text: "Руна бури ×2: +20% к сопротивлению молнии" }] } },
      { slot: "Кольцо", pos: "ring1", label: "Кольцо", img: "i-ring", rarity: "rare",
        card: { kind: "rare", name: "Петля Рока", sub: "Аметистовое кольцо · ур. 74", mods: ["+71 к максимуму энергетического щита", "+33% к сопротивлению огню", "+12% к сопротивлению хаосу"] } },
      { slot: "Кольцо", pos: "ring2", label: "Кольцо", img: "i-ring2", rarity: "rare", tip: "left",
        card: { kind: "rare", name: "Кольцо Ветров", sub: "Кольцо Разлома · ур. 77", mods: ["+18% к урону от холода", "+29% к сопротивлению молнии", "+9% к скорости атаки"] } },
      { slot: "Перчатки", pos: "gloves", label: "Перчатки", img: "i-gloves", rarity: "unique", runes: ["rune-desert"], tip: "right",
        card: { kind: "unique", name: "Рука Чаюлы", sub: "Перчатки · ур. 65", mods: ["+72 к максимуму энергетического щита", "Критические удары замораживают врагов", "12% повышение скорости атаки"], desc: "«Тьма помнит каждое касание»." } },
      { slot: "Сапоги", pos: "boots", label: "Сапоги", img: "i-boots", rarity: "rare", runes: ["rune-desert"], tip: "left",
        card: { kind: "rare", name: "Поступь Бури", sub: "Сапоги · ур. 70", mods: ["30% повышение скорости передвижения", "+71 к максимуму энергетического щита", "+29% к сопротивлению огню"],
          runes: [{ img: "rune-desert", text: "Руна пустыни: +12% к сопротивлению огню" }] } },
      { slot: "Пояс", pos: "belt", label: "Пояс", img: "i-belt", rarity: "rare",
        card: { kind: "rare", name: "Узел Жил", sub: "Тяжёлый пояс · ур. 66", mods: ["+64 к максимуму энергетического щита", "+38% к сопротивлению огню", "20% повышение заряда флаконов"] } },
      { slot: "Флакон", pos: "flask1", label: "Флакон здоровья", img: "i-flask-life", rarity: "magic" },
      { slot: "Флакон", pos: "flask2", label: "Флакон маны", img: "i-flask-mana", rarity: "magic" },
      { slot: "Оберег", pos: "charm1", label: "Оберег", img: "i-charm", rarity: "magic" },
      { slot: "Оберег", pos: "charm2", label: "Оберег", img: "i-charm2", rarity: "magic" },
      { slot: "Оберег", pos: "charm3", label: "Оберег", img: "i-charm3", rarity: "magic" },
    ],
    gearSummary: "14 вещей · 8 рун",
    links: [{ label: "Twitch", icon: "stream", href: "#twitch" }, { label: "YouTube", icon: "play", href: "#youtube" }],
    reviews: {
      avg: 4.6, n: 38, dist: [[5, 26], [4, 8], [3, 3], [2, 0], [1, 1]],
      crit: [["sword", "Урон", 4.8], ["shield", "Живучесть", 4.0], ["coins", "Бюджет", 4.7], ["run", "Лёгкость игры", 4.3]],
      items: [
        { nick: "IceIsNice", hue: 185, cls: "monk", clsName: "Монах", level: 88, stars: 5, when: "3 дня назад", helpful: 24, voted: true,
          crit: [["Урон", 5], ["Живучесть", 4], ["Бюджет", 5], ["Лёгкость", 4]],
          text: "Прошёл кампанию за вечер и спокойно зашёл в карты. Без «Руки Чаюлы» урона хватает примерно до 10-го тира, дальше уже нужна. Заморозка правда спасает на боссах.",
          reply: { text: "Спасибо! Если умираешь на ранних картах — проверь сопротивление огню, оно чаще всего проседает.", when: "2 дня назад" } },
        { nick: "Granatnik", hue: 22, cls: "monk", clsName: "Монах", level: 71, stars: 4, when: "неделю назад", helpful: 9,
          text: "Урон отличный, но с одной единицей здоровья страшно на картах с хаосом и кровотечением. Добавил бы в описание, какие флаконы и обереги брать." },
        { nick: "NoobSaibot", hue: 60, cls: "monk", clsName: "Монах", level: 54, stars: 3, when: "2 недели назад", helpful: 3,
          text: "Для новичка сложновато: долго не понимал, когда переходить с каскада на удар. В приложении прокачка это объясняет, а здесь только коротко." },
      ],
    },
    followers: 860,
    views: 12400,
  },
};
