"use strict";
// Interface texts. Game text (mod lines, skill and item names) stays as in PoB's data, which is English.

const I18N = {
  ru: {
    builds: "Билды", loadingList: "загрузка…", noBuilds: "билдов нет", refresh: "обновить список",
    savedInPob: "сохранён в PoB", pobCode: "PoB-код", withProfile: "профиль",
    aiOn: (m) => `ИИ: ${m}`, aiOff: "ИИ не настроен",
    mainSkill: "Основной скилл", goal: "Цель", mode_damage: "урон", mode_balanced: "баланс", mode_defence: "защита",
    tab_overview: "Обзор", tab_damage: "Урон", tab_gear: "Снаряжение", tab_compare: "Сравнить предмет",
    tab_mechanics: "Механики", tab_profile: "Профиль", tab_assistant: "Ассистент",
    pickBuild: "Выберите билд слева",
    pickBuildHint: "Импортируйте персонажа в Path of Building (Import/Export Build → Authorize with Path of Exile → импорт → Save) — он появится в списке. Или положите PoB-код в builds/имя.txt.",
    opening: "Открываю билд в Path of Building…", openFailed: "Не удалось открыть билд", error: "Ошибка",
    level: (n) => `${n} уровень`,
    calcReport: "Считаю отчёт (~5 с)…",
    dps: "DPS", life: "Жизнь", hitChance: "Попадание", recovery: "Лечение", perSec: " /с", whileAttacking: "пока атакуешь",
    dpsRangeNote: "без дебаффов на враге … со всеми",
    hitsTitle: "Какой удар монстра ты переживёшь",
    hitsSub: (p) => `С полной жизни. Моб ${p.enemy_level} ур.; «сочная» карта: +${p.damage_pct}% урона и +${p.crit_bonus}% к криту монстров.`,
    hitNormal: "обычный", hitCrit: "крит", hitJuiced: "крит на сочной карте",
    issuesTitle: "Что сломано и где дыры", issuesSub: "«Сломано» — в игре не работает, хотя PoB считает.",
    lvl_must: "сломано", lvl_priority: "главное", lvl_warn: "учесть",
    supportsAtRisk: "Один из этих саппортов в игре выключен — цена, если это он:",
    pathTitle: "Путь апгрейда", pathSub: "Каждый шаг пересчитан с учётом предыдущих. Один мод ≈ один средний аффикс.",
    noEffect: "почти без эффекта",
    m_dps: "DPS", m_phys: "физ-удар", m_fire: "огонь", m_cold: "холод", m_lightning: "молния", m_chaos: "хаос-удар", m_recovery: "лечение",
    dmg_Physical: "Физ", dmg_Fire: "Огонь", dmg_Cold: "Холод", dmg_Lightning: "Молния", dmg_Chaos: "Хаос",
    coreTitle: "Ядро урона",
    resourceLine: (x) => `${x.name}: ${x.counted ? `считаю ${x.assumed} из ${x.maximum}` : "в билде не учитываются"}. DPS без них ${x.without}, с ними ${x.with} (×${x.mult})${x.ehp ? "; " + x.ehp : ""}.`,
    res_Rage: "Свирепость", res_PowerCharges: "Заряды энергии", res_FrenzyCharges: "Заряды ярости",
    res_EnduranceCharges: "Заряды выносливости",
    rageEmpty: " В самом PoB поле свирепости пустое — его левая панель показывает DPS без свирепости.",
    rate: (u, v) => `Курс: 1 ед. «${u}» = ${v} DPS`, colMod: "мод", colUnits: "в единицах", colEffect: "эффект", colScore: "очки",
    condTitle: "Условия боя",
    range: (lo, hi, x) => ["Вилка урона: ", lo, " без дебаффов на враге … ", hi, ` (×${x}) со всеми сразу.`],
    condOff: "Выключены в PoB — если в игре это обычно правда, урон выше:", condOn: "Включены — PoB считает выполненными:",
    investTitle: "Куда вкладываться", investSub: "Ценность одного типичного аффикса для выбранной цели.",
    calcGear: "Разбираю аффиксы, путь крафта и сокеты (~20 с, дальше из кэша)…",
    craftTitle: "Путь крафта по всем слотам", craftSub: "Только предметы без порчи. Целевой набор аффиксов, не процедура крафта.",
    craftAdd: "докрафтить ", from: "откуда: ", nothingToCraft: "Улучшать крафтом нечего.",
    socketsTitle: "Руны и соул-коры", socketsSub: "Предметы с порчей пропущены.", prices: (l) => ` Цены: poe.ninja, ${l}.`,
    socketNow: (i) => ` сокет ${i}: сейчас `, gives: (v) => ` (даёт ${v})`, nothingBetter: "лучше текущей вставки ничего нет",
    noSockets: "Сокетов на предметах, которые можно менять, нет.",
    slots: "Слоты", corrupted: "с порчей", craftable: "можно крафтить",
    affixCount: (p) => `${p.base}, ур. ${p.item_level} · префиксы ${p.prefixes}/${p.limit}, суффиксы ${p.suffixes}/${p.limit}`,
    approx: " (приблизительно)", prefix: "преф", suffix: "суфф", holds: "держит: ", utility: "утилити — PoB не оценивает",
    candidate: "Предмет-кандидат", slot: "Слот",
    candidatePh: "Вставьте предмет из игры (Ctrl+C на предмете) или отредактируйте текущий…",
    breakeven: "Точка безубыточности (необязательно)", breakevenPh: "строка мода кандидата, например: Adds 26 to 42 Physical Damage",
    compare: "Сравнить", insertCurrent: "Вставить надетый для правки", counting: "Считаю…",
    better: "лучше по урону", worse: "хуже по урону", same: "по урону примерно так же",
    verdict: (v) => `Кандидат против надетого: ${v}`, lifeDelta: (v) => `Жизнь ${v}`,
    reqShort: (a, h, n) => `не хватит ${a}: ${h} из ${n}`,
    beOk: (line, pct) => `Не хуже надетого, пока строка не ниже «${line}» (${pct}% от указанной).`,
    beBad: "Хуже надетого даже с полной строкой.",
    collecting: "Собираю механики из данных игры…",
    gapsTitle: "Что PoB не считает",
    gapsSub: "Статы и строки есть в данных игры, но в расчёт PoB не попадают. Важное — учесть поправкой в профиле.",
    other: (n) => `Прочее (${n})`, skillsTitle: "Скиллы и уникальные предметы",
    skillsSub: "Описания из данных игры — то, что получает ИИ-ассистент.", group: "группа",
    factsTitle: "Факты об игре", factsSub: "То, что игрок знает, а PoB — нет. Применяется ко всем расчётам.",
    rageMax: " свирепость всегда в максимуме", otherwise: "иначе:", manaOk: " мана держится в игре (не проверять дефицит маны)",
    correctionsTitle: "Поправки на механики, которых нет в PoB", corrMod: "строка мода (как в PoB)", corrUptime: "аптайм 0…1",
    confirmed: " подтверждено", remove: "убрать", addCorrection: "+ поправка", notes: "Заметки",
    save: "Сохранить и пересчитать", saved: "Профиль сохранён, билд пересчитан", howCounted: "Как сейчас считается",
    aiTitle: "Настройки ИИ",
    aiSub: "Ассистент получает билд, профиль и механики из данных игры заранее, а все цифры считает через движок PoB.",
    provider: "Провайдер", model: "Модель", apiUrl: "Адрес API", apiKey: "Ключ API",
    keySaved: (h) => `ключ сохранён (${h}) — оставьте поле пустым, чтобы не менять`, keyPh: "вставьте ключ",
    noKeyNeeded: "ключ не нужен", modelPh: "название модели", loadModels: "Загрузить список моделей",
    saveAi: "Сохранить", clearKey: "Удалить ключ", aiSaved: "Настройки ИИ сохранены",
    modelsLoaded: (n) => `Моделей: ${n}`, modelsHint: "Модель должна поддерживать вызов инструментов (tool calling).",
    keyStorage: "Ключ хранится только на этом компьютере (%APPDATA%\\poe2lab\\llm.json) и не попадает в репозиторий.",
    dataLeaves: "Данные билда и вопросы уходят выбранному провайдеру.",
    chatHello: "Спросите о билде: что улучшить, стоит ли брать предмет, почему умираете. Механику билда я уже знаю из данных игры и вашего профиля.",
    chatPh: "Например: что даст больше урона за дешёво?", ask: "Спросить", thinking: "Думаю и считаю…",
    computed: "посчитано: ", proposal: "Ассистент предложил поправку профиля — посмотрите вкладку «Профиль»",
    resetChat: "Новый разговор", configureFirst: "Сначала настройте провайдера и ключ выше.",
    noProfileYet: (n) => `У билда «${n}» профиля ещё нет — ниже значения по умолчанию. Профиль создастся при сохранении.`,
    changeMod: "выбрать другой мод", modSearchPh: "начните вводить мод: например «скорость умений» или «skill speed»",
    modSearching: "ищу…", modNothing: "ничего не найдено",
  },
  en: {
    builds: "Builds", loadingList: "loading…", noBuilds: "no builds", refresh: "refresh list",
    savedInPob: "saved in PoB", pobCode: "PoB code", withProfile: "profile",
    aiOn: (m) => `AI: ${m}`, aiOff: "AI not configured",
    mainSkill: "Main skill", goal: "Goal", mode_damage: "damage", mode_balanced: "balanced", mode_defence: "defence",
    tab_overview: "Overview", tab_damage: "Damage", tab_gear: "Gear", tab_compare: "Compare item",
    tab_mechanics: "Mechanics", tab_profile: "Profile", tab_assistant: "Assistant",
    pickBuild: "Pick a build on the left",
    pickBuildHint: "Import your character in Path of Building (Import/Export Build → Authorize with Path of Exile → import → Save) and it appears in the list. Or put a PoB code in builds/name.txt.",
    opening: "Opening the build in Path of Building…", openFailed: "Could not open the build", error: "Error",
    level: (n) => `level ${n}`,
    calcReport: "Computing the report (~5 s)…",
    dps: "DPS", life: "Life", hitChance: "Hit chance", recovery: "Recovery", perSec: " /s", whileAttacking: "while attacking",
    dpsRangeNote: "no enemy debuffs … all of them",
    hitsTitle: "Largest monster hit you survive",
    hitsSub: (p) => `From full life. Level ${p.enemy_level} monster; juiced map: +${p.damage_pct}% damage and +${p.crit_bonus}% monster crit bonus.`,
    hitNormal: "normal", hitCrit: "crit", hitJuiced: "crit on a juiced map",
    issuesTitle: "What is broken and where the gaps are", issuesSub: "“Broken” means it does not work in game although PoB counts it.",
    lvl_must: "broken", lvl_priority: "main", lvl_warn: "note",
    supportsAtRisk: "One of these supports is disabled in game — its cost if it is this one:",
    pathTitle: "Upgrade path", pathSub: "Each step is recomputed after the previous ones. One mod ≈ one average affix.",
    noEffect: "barely any effect",
    m_dps: "DPS", m_phys: "phys hit", m_fire: "fire", m_cold: "cold", m_lightning: "lightning", m_chaos: "chaos hit", m_recovery: "recovery",
    dmg_Physical: "Phys", dmg_Fire: "Fire", dmg_Cold: "Cold", dmg_Lightning: "Lightning", dmg_Chaos: "Chaos",
    coreTitle: "Damage core",
    resourceLine: (x) => `${x.name}: ${x.counted ? `assuming ${x.assumed} of ${x.maximum}` : "not counted in the build"}. DPS without ${x.without}, with ${x.with} (×${x.mult})${x.ehp ? "; " + x.ehp : ""}.`,
    res_Rage: "Rage", res_PowerCharges: "Power Charges", res_FrenzyCharges: "Frenzy Charges",
    res_EnduranceCharges: "Endurance Charges",
    rageEmpty: " The Rage field in PoB itself is empty — its sidebar shows DPS without Rage.",
    rate: (u, v) => `Rate: 1 point of “${u}” = ${v} DPS`, colMod: "mod", colUnits: "in points", colEffect: "effect", colScore: "score",
    condTitle: "Combat conditions",
    range: (lo, hi, x) => ["Damage range: ", lo, " with no enemy debuffs … ", hi, ` (×${x}) with all of them.`],
    condOff: "Off in PoB — if usually true in game, damage is higher:", condOn: "On — PoB assumes them:",
    investTitle: "Where to invest", investSub: "Value of one typical affix for the chosen goal.",
    calcGear: "Analysing affixes, crafting path and sockets (~20 s, cached afterwards)…",
    craftTitle: "Crafting path across slots", craftSub: "Uncorrupted items only. A target affix set, not a crafting procedure.",
    craftAdd: "craft ", from: "from: ", nothingToCraft: "Nothing to improve by crafting.",
    socketsTitle: "Runes and soul cores", socketsSub: "Corrupted items are skipped.", prices: (l) => ` Prices: poe.ninja, ${l}.`,
    socketNow: (i) => ` socket ${i}: now `, gives: (v) => ` (gives ${v})`, nothingBetter: "nothing beats the current one",
    noSockets: "No sockets on items that can be changed.",
    slots: "Slots", corrupted: "corrupted", craftable: "craftable",
    affixCount: (p) => `${p.base}, ilvl ${p.item_level} · prefixes ${p.prefixes}/${p.limit}, suffixes ${p.suffixes}/${p.limit}`,
    approx: " (approximate)", prefix: "pre", suffix: "suf", holds: "holds: ", utility: "utility — PoB does not value it",
    candidate: "Candidate item", slot: "Slot",
    candidatePh: "Paste an item from the game (Ctrl+C on it) or edit the equipped one…",
    breakeven: "Breakeven (optional)", breakevenPh: "a mod line of the candidate, e.g. Adds 26 to 42 Physical Damage",
    compare: "Compare", insertCurrent: "Insert equipped item to edit", counting: "Computing…",
    better: "better damage", worse: "worse damage", same: "about the same damage",
    verdict: (v) => `Candidate vs equipped: ${v}`, lifeDelta: (v) => `Life ${v}`,
    reqShort: (a, h, n) => `${a} short: ${h} of ${n}`,
    beOk: (line, pct) => `Not worse than equipped while the line stays at least “${line}” (${pct}% of it).`,
    beBad: "Worse than equipped even with the full line.",
    collecting: "Collecting mechanics from game data…",
    gapsTitle: "What PoB does not calculate",
    gapsSub: "These stats and lines are in the game data but PoB ignores them. Record the important ones as profile corrections.",
    other: (n) => `Other (${n})`, skillsTitle: "Skills and unique items",
    skillsSub: "Descriptions from game data — what the AI assistant receives.", group: "group",
    factsTitle: "Facts about your play", factsSub: "What you know and PoB does not. Applied to every calculation.",
    rageMax: " Rage is always at maximum", otherwise: "otherwise:", manaOk: " mana is sustained in game (skip mana deficit checks)",
    correctionsTitle: "Corrections for mechanics PoB lacks", corrMod: "mod line (PoB wording)", corrUptime: "uptime 0…1",
    confirmed: " confirmed", remove: "remove", addCorrection: "+ correction", notes: "Notes",
    save: "Save and recalculate", saved: "Profile saved, build recalculated", howCounted: "Current assumptions",
    aiTitle: "AI settings",
    aiSub: "The assistant gets the build, profile and game-data mechanics up front and computes every number with the PoB engine.",
    provider: "Provider", model: "Model", apiUrl: "API URL", apiKey: "API key",
    keySaved: (h) => `key saved (${h}) — leave empty to keep it`, keyPh: "paste the key",
    noKeyNeeded: "no key needed", modelPh: "model name", loadModels: "Load model list",
    saveAi: "Save", clearKey: "Delete key", aiSaved: "AI settings saved",
    modelsLoaded: (n) => `Models: ${n}`, modelsHint: "The model must support tool calling.",
    keyStorage: "The key stays on this computer (%APPDATA%\\poe2lab\\llm.json) and never goes into the repository.",
    dataLeaves: "Build data and questions are sent to the chosen provider.",
    chatHello: "Ask about the build: what to improve, whether an item is worth it, why you die. I already know the build's mechanics from game data and your profile.",
    chatPh: "E.g.: what gives the most damage cheaply?", ask: "Ask", thinking: "Thinking and computing…",
    computed: "computed: ", proposal: "The assistant proposed a profile correction — see the Profile tab",
    resetChat: "New conversation", configureFirst: "Configure a provider and key above first.",
    noProfileYet: (n) => `Build “${n}” has no profile yet — defaults below. Saving creates it.`,
    changeMod: "pick another mod", modSearchPh: "start typing a mod, e.g. “skill speed”",
    modSearching: "searching…", modNothing: "nothing found",
  },
};

const SLOT_RU = {
  "Weapon 1": "Оружие", "Weapon 2": "Вторая рука", "Weapon 1 Swap": "Оружие (второй набор)",
  "Weapon 2 Swap": "Вторая рука (второй набор)", "Helmet": "Шлем", "Body Armour": "Нательная броня",
  "Gloves": "Перчатки", "Boots": "Ботинки", "Amulet": "Амулет", "Ring 1": "Кольцо 1", "Ring 2": "Кольцо 2",
  "Ring 3": "Кольцо 3", "Belt": "Пояс", "Charm 1": "Оберег 1", "Charm 2": "Оберег 2", "Charm 3": "Оберег 3",
  "Flask 1": "Флакон жизни", "Flask 2": "Флакон маны",
};

const STATE_RU = {
  "Shocked": "под шоком", "Crushed": "сокрушён", "Intimidated": "запуган", "Pinned": "пригвождён",
  "Heavy Stunned": "в тяжёлом оглушении", "Blinded": "ослеплён", "Maimed": "покалечен", "covered in Ash": "покрыт пеплом",
  "covered in Frost": "покрыт инеем", "Debilitated": "ослаблен", "Frozen": "заморожен", "Chilled": "охлаждён",
  "Ignited": "подожжён", "Burning": "горит", "Dazed": "ошеломлён", "Hindered": "замедлен", "on Low Life": "при низкой жизни",
  "Unnerved": "деморализован", "Bleeding": "кровоточит", "Poisoned": "отравлен", "Rare?": "редкий",
};
const BUFF_RU = {
  "Adrenaline": "Адреналин", "Onslaught": "Натиск", "Unholy Might": "Нечестивая мощь", "Chaotic Might": "Хаотическая мощь",
  "Arcane Surge": "Магический прилив", "Fortify": "Укрепление",
};
const PHRASE_RU = {
  "Are you on Consecrated Ground?": "Стоишь на освящённой земле?",
  "Are you Sprinting?": "Бежишь (спринт)?",
  "Is the skill Empowered?": "Скилл усилен (Empowered)?",
  "Moved 2m during Skill use?": "Сдвинулся на 2 м во время скилла?",
  "Have you been Stunned Recently?": "Был оглушён недавно?",
  "Currently Shapeshifted?": "Сейчас в облике зверя?",
  "Shapeshifted to animal recently?": "Недавно превращался в зверя?",
  "Shapeshifted to human recently?": "Недавно возвращался в облик человека?",
  "Infusion consumed recently?": "Недавно поглощён Infusion?",
  "Have you Triggered a skill Recently?": "Недавно срабатывал скилл-триггер?",
  "Enemy Max Resistance is always 75%": "Максимальное сопротивление врага всегда 75%",
  "Ignore Jewel Limits": "Игнорировать лимиты самоцветов",
  "Do you use Power Charges?": "Используешь заряды силы?",
  "Do you use Frenzy Charges?": "Используешь заряды ярости?",
  "Do you use Endurance Charges?": "Используешь заряды выносливости?",
};

const CLASS_RU = {
  "Warrior": "Воин", "Monk": "Монах", "Ranger": "Следопыт", "Huntress": "Охотница", "Sorceress": "Волшебница",
  "Witch": "Ведьма", "Mercenary": "Наёмник", "Druid": "Друид", "Titan": "Титан", "Warbringer": "Вестник войны",
  "Smith of Kitava": "Кузнец Китавы", "Invoker": "Заклинатель", "Martial Artist": "Мастер боевых искусств",
  "Acolyte of Chayula": "Послушник Чаюлы", "Deadeye": "Меткий стрелок", "Pathfinder": "Следопыт",
  "Stormweaver": "Повелитель бурь", "Chronomancer": "Хрономант", "Infernalist": "Инферналист",
  "Blood Mage": "Маг крови", "Lich": "Лич", "Tactician": "Тактик", "Witchhunter": "Охотник на ведьм",
  "Gemling Legionnaire": "Легионер-самоцвет", "Amazon": "Амазонка", "Ritualist": "Ритуалист",
  "Shaman": "Шаман", "Oracle": "Оракул",
};

// ---------- official game texts (stat templates and names from GGG's trade data) ----------
let GAME = { stats: {}, names: {} };
let BUILD_NAMES = [];  // names occurring in the open build, longest first, for free-text replacement

const TOKEN_RE = /[+-]?\(\s*-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?\s*\)|[+-]?\d+(?:\.\d+)?/g;
const statKey = (s) => s.replace(TOKEN_RE, "#").replace(/\+#/g, "#").replace(/\s+/g, " ").trim().toLowerCase();

function fillTemplate(tpl, line) {
  const tokens = line.match(TOKEN_RE) || [];
  if ((tpl.match(/#/g) || []).length !== tokens.length) return null;
  let i = 0;
  let out = "";
  for (let p = 0; p < tpl.length; p++) {
    if (tpl[p] !== "#") { out += tpl[p]; continue; }
    const tok = tokens[i++];
    out += p > 0 && (tpl[p - 1] === "+" || tpl[p - 1] === "-") ? tok.replace(/^[+-]/, "") : tok;
  }
  return out;
}

async function loadGameTexts() {
  GAME = { stats: {}, names: {} };
  if (LANG === "en") return;
  try { GAME = await (await fetch(`/api/i18n/${LANG}`)).json(); } catch (_) { /* offline: English game text */ }
}

// a mod line, or several joined with " / "
function trMod(line) {
  if (LANG === "en" || !line) return line;
  return line.split(" / ").map((part) => {
    const tpl = GAME.stats[statKey(part)];
    return (tpl && fillTemplate(tpl, part)) || part;
  }).join(" / ");
}

function trName(name) {
  if (LANG === "en" || !name) return name;
  return GAME.names[name] || CLASS_RU[name] || name;
}

// "Random Name, Base Type" for rares / "Unique Name, Base Type" for uniques
function trItem(name) {
  if (LANG === "en" || !name) return name;
  const parts = name.split(", ");
  if (parts.length !== 2) return trName(name);
  const [first, base] = parts;
  return GAME.names[first] ? `${GAME.names[first]}, ${trName(base)}` : trName(base);
}

function setBuildNames(build) {
  const names = new Set();
  for (const g of build.groups || []) g.skills.forEach((s) => names.add(s));
  for (const g of build.gems || []) names.add(g);
  for (const it of build.items || []) { it.name.split(", ").forEach((p) => names.add(p)); names.add(it.baseName); }
  BUILD_NAMES = [...names].filter((n) => n && GAME.names[n]).sort((a, b) => b.length - a.length);
}

const SUPPORT_COLOR_RU = { Strength: "красных", Dexterity: "зелёных", Intelligence: "синих" };

// server-made sentences: translate «quoted mods», support-gem counts and names from the open build
function trFree(text) {
  if (LANG === "en" || !text) return text;
  let s = text.replace(/«([^»]+)»/g, (_, inner) => `«${GAME.names[inner] ? GAME.names[inner] : trMod(inner)}»`);
  s = s.replace(/(\d+) (Strength|Dexterity|Intelligence) Support Gems/g, (_, n, c) => `${n} ${SUPPORT_COLOR_RU[c]} камней поддержки`);
  for (const n of BUILD_NAMES) s = s.split(n).join(GAME.names[n]);
  for (const [en, ru] of Object.entries(SLOT_RU)) s = s.split(`(${en})`).join(`(${ru})`);
  for (const [re, ru] of FREE_RU) s = s.replace(re, ru);
  return s;
}

const RES_RU = { Fire: "огню", Cold: "холоду", Lightning: "молнии" };
const ATTR_GEN_RU = { Str: "силы", Dex: "ловкости", Int: "интеллекта" };
const FREE_RU = [
  [/кап резиста (Fire|Cold|Lightning)/g, (_, r) => `кап сопротивления ${RES_RU[r]}`],
  [/требования (Str|Dex|Int)\b/g, (_, a) => `требования ${ATTR_GEN_RU[a]}`],
  [/Не хватает spirit/g, "Не хватает духа"],
  [/spirit на резервы/g, "дух на резервы"],
  [/\bspirit\b/gi, "дух"],
  [/Druidic Prowess/g, "друидическая доблесть"],
  [/ ?(?:стат )?[a-z0-9%+]+(?:_[a-z0-9%+]+){2,}/g, ""],  // internal stat ids: no use to a player
  [/Custom Modifiers/g, "пользовательские модификаторы"],
];

// "обычный ролл: MOD (нужен уровень предмета N+)" / "эссенция NAME: MOD — price" / "desecration: MOD"
function trSource(src) {
  if (LANG === "en") return src;
  let m = src.match(/^обычный ролл: (.+?)( \(нужен уровень предмета \d+\+\))?$/);
  if (m) return `обычный ролл: ${trMod(m[1])}${m[2] || ""}`;
  m = src.match(/^эссенция (.+?): (.+?)( — .+)?$/);
  if (m) return `эссенция ${trName(m[1])}: ${trMod(m[2])}${m[3] || ""}`;
  m = src.match(/^desecration: (.+)$/);
  if (m) return `осквернение: ${trMod(m[1])}`;
  return trFree(src);
}

let LANG = "ru";
try { LANG = localStorage.getItem("poe2lab.lang") || "ru"; } catch (_) { /* storage blocked */ }

function t(key, ...args) {
  const v = (I18N[LANG] && I18N[LANG][key]) ?? I18N.ru[key] ?? key;
  return typeof v === "function" ? v(...args) : v;
}

function slotName(s) { return LANG === "ru" ? (SLOT_RU[s] || s) : s; }

function conditionLabel(label) {
  if (LANG !== "ru") return label;
  if (PHRASE_RU[label]) return PHRASE_RU[label];
  let m = label.match(/^Is the enemy (.+?)\??$/);
  if (m) return `Враг ${STATE_RU[m[1]] || m[1]}?`;
  m = label.match(/^Do you have (.+?)\?$/);
  if (m) return `Есть ${BUFF_RU[m[1]] || m[1]}?`;
  m = label.match(/^Act (\d+): (.+)$/);
  if (m) return `Акт ${m[1]}: ${m[2]}`;
  m = label.match(/^Interlude (\d+): (.+)$/);
  if (m) return `Интерлюдия ${m[1]}: ${m[2]}`;
  return label;
}
