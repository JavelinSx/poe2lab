"use strict";
// Interface texts. Game text (mod lines, skill and item names) stays as in PoB's data, which is English.

const I18N = {
  ru: {
    builds: "Билды", loadingList: "загрузка…", noBuilds: "билдов нет", refresh: "обновить список",
    savedInPob: "сохранён в PoB", pobCode: "PoB-код", withProfile: "профиль",
    addBuild: "+ добавить билд", addTitle: "Добавить билд",
    fbButton: "✉ сообщить о нестыковке", fbTitle: "Сообщить о нестыковке",
    fbSub: "Число не сходится с игрой или PoB, непонятная подсказка, ошибка — напиши, письмо уйдёт автору poe2lab. Лучше всего: где смотрел, что увидел, что ожидал и откуда (PoB, игра).",
    fbMessagePh: "Что не так и где: вкладка, строка, какое число ожидал и откуда…",
    fbDrop: "Скрины: Ctrl+V, перетащи сюда или нажми, чтобы выбрать файл",
    fbDropHint: (n) => `Win+Shift+S — вырезать часть экрана, затем Ctrl+V здесь. До ${n} скринов.`,
    fbContactPh: "почта или Discord, если хочешь ответ (необязательно)", fbRemoveShot: "убрать скрин",
    fbWhat: "Вместе с письмом уйдёт:", fbWhatBuild: (n) => `билд «${n}» — PoB-код (и дерево с планом, если ты его менял)`,
    fbWhatNoBuild: "билд, открытый сейчас", fbWhatProfile: "профиль билда: факты и поправки",
    fbWhatContext: "вкладка, цель, основной скилл, язык и версия poe2lab", fbWhatShots: "скрины, которые ты добавишь",
    fbWhatNot: "Больше ничего: ключ ИИ, другие билды и файлы с компьютера не отправляются.",
    fbSend: "Отправить", fbSending: "Отправляю…", fbSent: "Спасибо! Отзыв отправлен.", fbEmpty: "Опиши, что не так",
    fbNeedBuild: "Сначала открой билд, в котором заметил нестыковку, — он уйдёт вместе с письмом.",
    fbOff: "В этой копии poe2lab отправка отзывов не настроена.",
    fbTooMany: (n) => `Не больше ${n} скринов`, fbBadImage: "Не удалось прочитать картинку",
    addSub: "Вставьте PoB-код (в PoB: Import/Export Build → Generate → Copy) или ссылку pobb.in.",
    addName: "имя (пусто — возьму класс и уровень из кода)", addCode: "PoB-код или ссылка https://pobb.in/…",
    addGo: "Добавить и открыть", adding: "добавляю…", added: (n) => `Билд «${n}» добавлен`,
    favOn: "в избранное", favOff: "убрать из избранного", removeBuild: "удалить из списка",
    confirmTrash: (n) => `Удалить билд «${n}»? Файл уйдёт в builds/.trash (вместе с профилем) — оттуда его можно вернуть.`,
    confirmHide: (n) => `Скрыть «${n}» из списка? Билд сохранён в самом PoB — его файл не удаляется.`,
    trashed: (n) => `«${n}» перемещён в builds/.trash`, hiddenOne: (n) => `«${n}» скрыт`,
    showHidden: (n) => `показать скрытые (${n})`, cancel: "Отмена",
    dmgType: "тип урона", weakest: "слабое место",
    immune: "иммунитет", notImmune: "нет иммунитета",
    tab_loot: "Лут-фильтр", lootLoading: "Подбираю базы и аффиксы под билд…",
    lootIntro: "Блок правил под этот билд ставится поверх твоего лут-фильтра: остальной фильтр работает как был. Фильтр PoE2 видит у неопознанной вещи только базу и уровень предмета, а у опознанной — названия аффиксов. Поэтому: подбери базу, опознай в инвентаре, выбрось — если вещь хорошая для билда, она подсветится «голдой».",
    lootWhat: "Что попадёт в фильтр", lootWhatSub: (m) => `По слотам билда. Нужные аффиксы — самые полезные для цели «${m}» моды на эту базу, их три лучших тира.`,
    lootBase: "База", lootIlvl: "Ур. предмета от", lootGold: "Голда — нужные моды", lootUnique: "уникальный предмет",
    lootByBase: "подсветка уника по базе (имя уника фильтр не видит)", lootNoMods: "нет модов, заметно влияющих на билд",
    lootAffixes: (n) => `в фильтре: ${n} названий аффиксов (лучшие тиры этих модов)`,
    lootLegend: "Оранжевая звезда + звук — «голда» (3+ нужных аффикса); оранжевый ромб — хорошая вещь (2+); оранжевый круг — неопознанная база билда, опознай; синий круг — белая/синяя база под крафт.",
    lootBuild: "Собрать фильтр", lootBuildSub: "Новый файл появится в папке фильтров игры. Твой исходный фильтр не меняется.",
    lootSrcFile: "Поверх фильтра из папки игры", lootSrcText: "Вставить текст фильтра", lootSrcNone: "Только блок билда",
    lootNoLocal: (d) => `В ${d} нет файлов .filter. Онлайн-фильтр по подписке сюда не попадает — вставь его текст или скачай файл (см. ниже).`,
    lootPastePh: "вставь сюда полный текст своего .filter", lootOnlyBlock: "Будет только блок билда: всё, что он не отметил, игра покажет как без фильтра.",
    lootName: "Имя нового фильтра", lootNamePh: "по умолчанию: «<твой фильтр> + poe2lab <билд>»",
    lootSave: "Собрать и сохранить", lootSaved: (n, p) => `Готово: ${p}. В игре: Настройки → Игра → Фильтр предметов → «${n}» (если игра запущена — нажми «Обновить» рядом со списком).`,
    lootSavedShort: (n) => `Фильтр «${n}» сохранён`,
    lootOnline: "Онлайн-фильтр (NeverSink, FilterBlade по подписке) игра хранит у себя, поэтому к нему нельзя дописать локально. Скачай его как файл (FilterBlade: Save/Download; NeverSink: GitHub) в папку фильтров или вставь текст выше. После обновления основного фильтра собери заново.",
    lootPreview: "Текст блока правил", copyBlock: "скопировать", copied: "Скопировано",
    ruTitle: "Часть названий — на английском", ruTitleOk: "Русские тексты из игры подключены",
    ruWhy: "Русские названия скиллов и пассивок, описания гемов, локации и иконки берутся из файлов установленной Path of Exile 2; названия модов — из справочника торговли GGG (нужен интернет). Пока их нет, интерфейс по-русски, а названия из PoB — по-английски.",
    ruNoGame: "Path of Exile 2 на этом компьютере не найдена: искал во всех библиотеках Steam и в папке клиента GGG. Если игра стоит в другом месте — укажите её папку ниже (ту, где лежит PathOfExileSteam.exe или PathOfExile.exe).",
    ruNoExtractor: (g) => `Игра найдена (${g}), но нет утилиты распаковки bun_extract_file (0,3 МБ, github.com/zao/ooz — её же использует Path of Building). Кнопка ниже скачает её и распакует тексты.`,
    ruNotUnpacked: (g) => `Игра найдена (${g}), тексты ещё не распакованы.`,
    ruError: (e) => `Последняя попытка не удалась: ${e}`,
    ruNoTrade: "Справочник торговли GGG недоступен (нет связи с pathofexile.com) — названия модов останутся английскими до следующего запуска с интернетом.",
    ruDirPh: "папка игры, например D:\\SteamLibrary\\steamapps\\common\\Path of Exile 2",
    ruUnpack: "Распаковать русские тексты", ruRebuild: "Распаковать заново", ruUnpacking: "Распаковываю (30–60 с)…",
    ruDone: "Русские тексты и иконки подключены", ruHide: "скрыть до следующего запуска",
    ruHint: "Файлы игры только читаются. После патча игры тексты обновятся сами при запуске.",
    ruStatusOk: "Тексты игры: русские ✓", ruStatusMissing: "Тексты игры: английские — почему?",
    take: "+ взять", drop: "− убрать", takeHint: "взять ноду вместе с путём до неё", dropHint: "снять ветку вместе с нодами, которые держатся только на ней",
    planTitle: "План дерева", planSub: (m) => `Правки дерева с пересчётом очков, урона и защиты. Автоперераспределение меняет слабые ветки на ноды, полезнее для цели «${m}», в тех же очках; каждое нажатие — случайный вариант.`,
    planEmpty: "Дерево как в билде. Нажми «+ взять» / «− убрать» в таблицах ниже или «Автоперераспределение».",
    planPoints: (u, b) => `Очки: ${u} из ${b}`, planOver: (n) => `— больше, чем в билде, на ${n}`,
    planVsBuild: "Против исходного дерева:", planLog: (n) => `Изменения (${n})`,
    planNote: "План живёт только в poe2lab: остальные вкладки считают по нему, пока не сбросишь. В PoB и игре ничего не меняется — «Сохранить как билд» добавит его в список, оттуда можно взять PoB-код.",
    optimize: "Автоперераспределение", optimizeMore: "Ещё вариант", optimizing: "Подбираю перераспределение (до минуты)…",
    optimized: (n) => `Нашёл замен: ${n}. Проверь снятые ноды — эффекты, которые PoB не считает, в расчёт не попали.`,
    optimizedNone: "Лучше этого дерева в тех же очках не нашёл — попробуй ещё раз или другую цель.",
    planReset: "Сбросить к билду", planSave: "Сохранить как билд", planSaved: (n) => `Сохранено как «${n}» — билд в списке слева`,
    oneShot: "убивает", oneShotHint: "с одного удара", hitsToDie: (n) => `${n} ${n === 1 ? "удар" : n < 5 ? "удара" : "ударов"}`,
    hitTooltip: (s, r) => `Переживаешь удар с базой до ${s}; типичный удар монстра — ${r}`,
    answerStyle: "Стиль ответов", styleShort: "Кратко — вывод и до 5 пунктов с цифрами", styleDetailed: "Подробно — вывод, почему, что сделать",
    answerStyleHint: "В обоих режимах цифры берутся только из расчёта PoB; то, что посчитать нельзя, помечается «(оценка)».",
    tab_tree: "Дерево", treeLoading: "Примеряю ноды дерева…", upToPoints: (n) => `до ${n} очков`, reach: "Дальность",
    keystone: "ключевое", notable: "значимое", node: "Нода", points: "Очков", perPoint: "Польза на очко", treeGives: "Что даёт",
    via: (list) => `по пути: ${list}`, alongWith: (list) => `вместе с ней уйдут: ${list}`, treeGrowth: "Куда расти",
    treeGrowthSub: (m) => `Значимые и ключевые пассивки в пределах выбранного числа очков, с учётом проходных нод. Цель: ${m}. Сортировка по пользе на одно очко.`,
    treeNothing: "В пределах этого числа очков нет значимых нод.", treeRespec: "Что можно перераспределить",
    treeRespecSub: "Взятые ветки, которые дают меньше на очко, чем лучший вариант роста выше. «Освободит» — сколько очков вернётся вместе с нодами, которые держатся только на этой.",
    branch: "Ветка", freed: "Освободит", youLose: "Потеряешь", treeNoRespec: "Все взятые ветки окупаются не хуже лучшего варианта роста.",
    treeUnseen: "PoB не видит эффекта этих нод", treeUnseenSub: "Снятие не меняет ни урон, ни защиту в PoB — обычно это механика, которую PoB не считает (скорость кличей, свирепость при ударе, эффекты на врагах). Проверь сам, прежде чем снимать.",
    treeAttributes: "Атрибутные ноды", treeAttributesSub: "Их польза — требования камней и предметов, PoB не переводит это в урон. Перед снятием смотри раздел атрибутов во «Обзоре».",
    pointsN: (n) => `${n} оч.`, treeIntro: (n) => `Взято нод основного дерева: ${n}. Цель переключается вверху (урон / баланс / защита).`,
    esRecoveryNote: "энергощит: перезарядка с учётом задержки, реген, похищение",
    dpsMinions: "DPS армии миньонов", minionsNote: (n, per) => `${n} активных × ${per} на одного`,
    lifeAndEs: "Здоровье + энергощит", lifeEsNote: "здоровье + энергетический щит",
    dmgFull_Physical: "Физический", dmgFull_Fire: "Огонь", dmgFull_Cold: "Холод", dmgFull_Lightning: "Молния", dmgFull_Chaos: "Хаос",
    hitsNote: "Больше процент — опаснее. Под процентом — сколько таких ударов подряд ты выдержишь до смерти. 100% и выше — удар убивает сразу с полного здоровья. Боссы бьют в разы сильнее обычных монстров. Наведи на число — увидишь самый сильный удар, который ты переживаешь.",
    cmpVersus: "С билдом-эталоном", cmpItem: "Предмет против надетого",
    refTitle: "Сравнение с эталоном", refSub: "Эталон — чужой готовый билд (например, из гайда) со своим шмотом. Покажу, насколько твои характеристики от него отстают, и что даст каждый его предмет в твоём билде.",
    refBuild: "Билд-эталон", pickRef: "— выберите билд —", refNone: "Добавьте билд-эталон кнопкой «+ добавить билд» слева.",
    refLoading: "Загружаю эталон и считаю…", refStats: "Характеристики",
    refStatsSub: (a, b) => `Каждый билд посчитан со своим профилем против моба 79 ур. Основной скилл: у тебя «${a}», у эталона «${b}».`,
    refSkillDiffers: "Основные скиллы разные — DPS сравним только приблизительно, защита сравнима полностью.",
    mine: "Мой билд", diffMine: "У меня", now: "Сейчас", change: "Изменение", withTheirGear: "С шмотом эталона",
    withCandidate: "С кандидатом",
    grp_offence: "Урон", grp_defence: "Защита", grp_resist: "Сопротивления", grp_hits: "Переживаемый удар",
    grp_attributes: "Атрибуты", grp_other: "Прочее",
    st_dps: "DPS", st_hitChance: "Шанс попадания", st_critChance: "Шанс крита", st_speed: "Атак/сотворений в секунду",
    st_life: "Здоровье", st_es: "Энергетический щит", st_mana: "Мана", st_ehp: "EHP (эффективный запас)", st_armour: "Броня",
    st_evasion: "Уклонение", st_res_Fire: "к огню", st_res_Cold: "к холоду", st_res_Lightning: "к молнии", st_res_Chaos: "к хаосу",
    st_hit_Physical: "физический", st_hit_Fire: "огонь", st_hit_Cold: "холод", st_hit_Lightning: "молния", st_hit_Chaos: "хаос",
    st_Str: "Сила", st_Dex: "Ловкость", st_Int: "Интеллект", st_spiritFree: "Свободный дух", st_moveSpeed: "Скорость передвижения",
    st_recovery: "Восстановление в бою, /с",
    refItems: "Предметы эталона в твоём билде", refItemsSub: "Каждый предмет эталона примерен в твой билд по отдельности (с твоим деревом и камнями).",
    ifWear: "Если надеть", refEmpty: "у эталона пусто", cannotEquip: "PoB не может надеть", wrongWeapon: "оружие не подходит к основному скиллу",
    details: "подробно", refAllGear: "Весь шмот эталона сразу", refAllGearSub: "Твой билд, если надеть все предметы эталона одновременно (пустые у него слоты — тоже пустые).",
    step1: "1. Что заменяем", step2: "2. Кандидат", equippedNow: "Надето сейчас:", slotEmpty: "Слот пустой",
    fromRef: (n) => `взять из эталона «${n}»`, loadedFromRef: (n) => `Предмет взят из эталона «${n}».`,
    breakevenHelp: "Вставьте строку мода кандидата — посчитаю, до какого значения она может упасть, чтобы предмет всё ещё был не хуже надетого. Полезно при покупке: какой минимальный ролл брать.",
    vBetter: "Лучше надетого", vWorse: "Хуже надетого", vSame: "Почти без разницы",
    vMixed: (d, h) => `Смешанно: урон ${d}, защита до ${h}`,
    addToPob: "добавить в расчёт PoB", searching: "подбираю…", pobReads: "PoB поймёт эту механику так:", addThis: "Добавить",
    orSimilar: "или похожий мод:", similarMods: "PoB не читает эту строку напрямую. Похожие моды, которые PoB считает:",
    orSearch: "или найдите нужный мод:", addHint: "Поправка добавится в профиль неподтверждённой, с аптаймом 100% — числа и аптайм можно поправить во вкладке «Профиль».",
    corrAdded: (m) => `Добавлено в профиль: «${m}». Расчёт обновлён.`,
    aiOn: (m) => `ИИ: ${m}`, aiOff: "ИИ не настроен",
    mainSkill: "Основной скилл", goal: "Цель", mode_damage: "урон", mode_balanced: "баланс", mode_defence: "защита",
    tab_overview: "Обзор", tab_damage: "Урон", tab_gear: "Снаряжение", tab_compare: "Сравнение",
    tab_mechanics: "Механики", tab_profile: "Профиль", tab_assistant: "Ассистент",
    pickBuild: "Выберите билд слева",
    pickBuildHint: "Нажмите «+ добавить билд» слева и вставьте PoB-код или ссылку pobb.in. Билды, сохранённые в самом Path of Building, появляются в списке сами.",
    opening: "Открываю билд в Path of Building…", openFailed: "Не удалось открыть билд", error: "Ошибка",
    level: (n) => `${n} уровень`,
    calcReport: "Считаю отчёт (~5 с)…",
    dps: "DPS", life: "Жизнь", hitChance: "Попадание", recovery: "Лечение", perSec: " /с", whileAttacking: "пока атакуешь",
    dpsRangeNote: "без дебаффов на враге … со всеми",
    hitsTitle: "Сколько снимает удар монстра",
    hitsSub: (p, ph, ch) => `Доля твоего запаса (здоровье + энергощит), которую снимает один тяжёлый удар обычного монстра ${p.enemy_level} ур. (база ${ph}, хаос ${ch}). Хард-карта: монстры наносят +${p.damage_pct}% урона и +${p.crit_bonus}% к бонусу крита.`,
    hitNormal: "обычный удар", hitCrit: "крит", hitJuiced: "крит на хард-карте",
    issuesTitle: "Что сломано и где дыры", issuesSub: "«Сломано» — в игре не работает, хотя PoB считает.",
    lvl_must: "сломано", lvl_priority: "главное", lvl_warn: "учесть",
    supportsAtRisk: "Один из этих саппортов в игре выключен — цена, если это он:",
    pathTitle: "Путь апгрейда", pathSub: "Каждый шаг пересчитан с учётом предыдущих. Один мод ≈ один средний аффикс.",
    noEffect: "почти без эффекта",
    m_dps: "DPS", m_ehp: "EHP (с уклонением)", m_phys: "физ-удар", m_fire: "огонь", m_cold: "холод", m_lightning: "молния", m_chaos: "хаос-удар", m_recovery: "лечение",
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
    approx: " (приблизительно)", prefix: "преф", suffix: "суфф", holds: "держит: ", utility: "служебный аффикс — PoB не оценивает",
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
    modelsLoaded: (n) => `Моделей: ${n}`, modelsHint: "Модель должна поддерживать вызов инструментов.",
    keyStorage: "Ключ хранится только на этом компьютере (%APPDATA%\\poe2lab\\llm.json) и не попадает в репозиторий.",
    dataLeaves: "Данные билда и вопросы уходят выбранному провайдеру.",
    chatHello: "Спросите о билде: что улучшить, стоит ли брать предмет, почему умираете. Механику билда я уже знаю из данных игры и вашего профиля.",
    chatPh: "Например: что даст больше урона за дешёво?", ask: "Спросить", thinking: "Думаю и считаю…",
    computed: "посчитано: ", proposal: "Ассистент предложил поправку профиля — посмотрите вкладку «Профиль»",
    resetChat: "Новый разговор", configureFirst: "Сначала настройте провайдера и ключ выше.",
    noProfileYet: (n) => `У билда «${n}» профиля ещё нет — ниже значения по умолчанию. Профиль создастся при сохранении.`,
    changeMod: "выбрать другой мод", modSearchPh: "начните вводить мод: например «скорость умений» или «skill speed»",
    modSearching: "ищу…", modNothing: "ничего не найдено",
    noQuestions: "Для этого билда общих вопросов нет — свирепости и трат маны у него нет. Ниже можно добавить поправки на механики.",
  },
  en: {
    builds: "Builds", loadingList: "loading…", noBuilds: "no builds", refresh: "refresh list",
    savedInPob: "saved in PoB", pobCode: "PoB code", withProfile: "profile",
    addBuild: "+ add build", addTitle: "Add a build",
    fbButton: "✉ report a problem", fbTitle: "Report a problem",
    fbSub: "A number that differs from the game or PoB, an unclear hint, an error — write it, the mail goes to the author of poe2lab. Best: where you looked, what you saw, what you expected and from where (PoB, the game).",
    fbMessagePh: "What is wrong and where: tab, line, the number you expected and where it comes from…",
    fbDrop: "Screenshots: Ctrl+V, drop here or click to choose a file",
    fbDropHint: (n) => `Win+Shift+S cuts a part of the screen, then Ctrl+V here. Up to ${n} screenshots.`,
    fbContactPh: "email or Discord if you want an answer (optional)", fbRemoveShot: "remove screenshot",
    fbWhat: "Sent with the message:", fbWhatBuild: (n) => `build “${n}” as a PoB code (and the planned tree, if you changed it)`,
    fbWhatNoBuild: "the build open now", fbWhatProfile: "the build profile: facts and corrections",
    fbWhatContext: "tab, goal, main skill, language and poe2lab version", fbWhatShots: "the screenshots you add",
    fbWhatNot: "Nothing else: the AI key, other builds and files on this computer are not sent.",
    fbSend: "Send", fbSending: "Sending…", fbSent: "Thanks! The report is sent.", fbEmpty: "Describe what is wrong",
    fbNeedBuild: "Open the build where you noticed the problem first — it goes with the message.",
    fbOff: "Sending reports is not set up in this copy of poe2lab.",
    fbTooMany: (n) => `At most ${n} screenshots`, fbBadImage: "Could not read the image",
    addSub: "Paste a PoB code (in PoB: Import/Export Build → Generate → Copy) or a pobb.in link.",
    addName: "name (empty: class and level from the code)", addCode: "PoB code or https://pobb.in/… link",
    addGo: "Add and open", adding: "adding…", added: (n) => `Build “${n}” added`,
    favOn: "add to favourites", favOff: "remove from favourites", removeBuild: "remove from the list",
    confirmTrash: (n) => `Remove build “${n}”? The file goes to builds/.trash with its profile — you can move it back.`,
    confirmHide: (n) => `Hide “${n}” from the list? It is saved in PoB itself — its file is not deleted.`,
    trashed: (n) => `“${n}” moved to builds/.trash`, hiddenOne: (n) => `“${n}” hidden`,
    showHidden: (n) => `show hidden (${n})`, cancel: "Cancel",
    dmgType: "damage type", weakest: "weak spot",
    immune: "immune", notImmune: "not immune",
    tab_loot: "Loot filter", lootLoading: "Picking bases and affixes for the build…",
    lootIntro: "A block of rules for this build goes on top of your loot filter; the rest of it works as before. PoE2 filters see an unidentified item's base and item level, and an identified item's affix names. So: pick up the base, identify it in the inventory, drop it — if it is good for the build it lights up as “gold”.",
    lootWhat: "What goes into the filter", lootWhatSub: (m) => `Per slot of the build. Wanted affixes are the most useful mods on that base for “${m}”, their three best tiers.`,
    lootBase: "Base", lootIlvl: "Item level from", lootGold: "Gold — wanted mods", lootUnique: "unique item",
    lootByBase: "unique highlighted by base (filters cannot see unique names)", lootNoMods: "no mods that matter to the build",
    lootAffixes: (n) => `in the filter: ${n} affix names (best tiers of these mods)`,
    lootLegend: "Orange star + sound — gold (3+ wanted affixes); orange diamond — good (2+); orange circle — unidentified build base, identify it; blue circle — white/blue crafting base.",
    lootBuild: "Build the filter", lootBuildSub: "A new file appears in the game's filter folder. Your own filter is not changed.",
    lootSrcFile: "On top of a filter in the game folder", lootSrcText: "Paste filter text", lootSrcNone: "Build block only",
    lootNoLocal: (d) => `No .filter files in ${d}. A subscribed online filter is not stored there — paste its text or download it as a file (see below).`,
    lootPastePh: "paste the full text of your .filter here", lootOnlyBlock: "Only the build block: whatever it does not mark is shown as without a filter.",
    lootName: "New filter name", lootNamePh: "default: “<your filter> + poe2lab <build>”",
    lootSave: "Build and save", lootSaved: (n, p) => `Done: ${p}. In game: Options → Game → Item Filter → “${n}” (with the game running, press Refresh next to the list).`,
    lootSavedShort: (n) => `Filter “${n}” saved`,
    lootOnline: "An online filter (NeverSink, FilterBlade subscription) is kept by the game, so nothing can be added to it locally. Download it as a file (FilterBlade: Save/Download; NeverSink: GitHub) into the filter folder or paste its text above. Rebuild after updating the main filter.",
    lootPreview: "Rule block text", copyBlock: "copy", copied: "Copied",
    ruTitle: "Some names are in English", ruTitleOk: "Russian game texts are connected",
    ruWhy: "Russian skill and passive names, gem descriptions, areas and icons come from the installed Path of Exile 2; mod names from GGG's trade data (needs internet).",
    ruNoGame: "Path of Exile 2 was not found: searched every Steam library and the GGG client folder. If it is elsewhere, enter its folder below (where PathOfExileSteam.exe or PathOfExile.exe is).",
    ruNoExtractor: (g) => `The game is found (${g}) but the bun_extract_file extractor is missing (0.3 MB, github.com/zao/ooz — the one Path of Building uses). The button below downloads it and unpacks the texts.`,
    ruNotUnpacked: (g) => `The game is found (${g}); the texts are not unpacked yet.`,
    ruError: (e) => `The last attempt failed: ${e}`,
    ruNoTrade: "GGG's trade data is unreachable (no connection to pathofexile.com) — mod names stay English until a run with internet.",
    ruDirPh: "game folder, e.g. D:\\SteamLibrary\\steamapps\\common\\Path of Exile 2",
    ruUnpack: "Unpack Russian texts", ruRebuild: "Unpack again", ruUnpacking: "Unpacking (30–60 s)…",
    ruDone: "Russian texts and icons connected", ruHide: "hide until next start",
    ruHint: "The game files are only read. After a game patch the texts update on start.",
    ruStatusOk: "Game texts: Russian ✓", ruStatusMissing: "Game texts: English — why?",
    take: "+ take", drop: "− drop", takeHint: "allocate the node with its path", dropHint: "remove the branch with the nodes only reachable through it",
    planTitle: "Tree plan", planSub: (m) => `Tree edits with points, damage and defence recalculated. Auto-respec trades weak branches for nodes better for “${m}” within the same points; every press is a random variant.`,
    planEmpty: "The tree is as in the build. Use “+ take” / “− drop” below or “Auto-respec”.",
    planPoints: (u, b) => `Points: ${u} of ${b}`, planOver: (n) => `— ${n} more than the build`,
    planVsBuild: "Against the original tree:", planLog: (n) => `Changes (${n})`,
    planNote: "The plan lives in poe2lab only: other tabs compute with it until reset. Nothing changes in PoB or the game — “Save as build” adds it to the list, with its PoB code.",
    optimize: "Auto-respec", optimizeMore: "Another variant", optimizing: "Searching for a respec (up to a minute)…",
    optimized: (n) => `Trades found: ${n}. Check the removed nodes — effects PoB does not model were not counted.`,
    optimizedNone: "Found nothing better within the same points — try again or another goal.",
    planReset: "Reset to the build", planSave: "Save as build", planSaved: (n) => `Saved as “${n}” — see the build list`,
    oneShot: "kills", oneShotHint: "in one hit", hitsToDie: (n) => `${n} hit${n === 1 ? "" : "s"}`,
    hitTooltip: (s, r) => `You survive a hit of up to ${s} base; a typical monster hit is ${r}`,
    answerStyle: "Answer style", styleShort: "Short — conclusion and up to 5 points with numbers", styleDetailed: "Detailed — conclusion, why, what to do",
    answerStyleHint: "Either way numbers come only from PoB's calculation; what cannot be computed is marked “(estimate)”.",
    tab_tree: "Tree", treeLoading: "Trying tree nodes…", upToPoints: (n) => `up to ${n} points`, reach: "Reach",
    keystone: "keystone", notable: "notable", node: "Node", points: "Points", perPoint: "Value per point", treeGives: "Gives",
    via: (list) => `on the way: ${list}`, alongWith: (list) => `goes together with: ${list}`, treeGrowth: "Where to grow",
    treeGrowthSub: (m) => `Notables and keystones within the chosen number of points, travel nodes included. Goal: ${m}. Sorted by value per point.`,
    treeNothing: "No notables within that many points.", treeRespec: "What could be respecced",
    treeRespecSub: "Allocated branches worth less per point than the best growth option above. “Frees” counts the node and everything only reachable through it.",
    branch: "Branch", freed: "Frees", youLose: "You lose", treeNoRespec: "Every allocated branch pays at least as well as the best growth option.",
    treeUnseen: "PoB sees no effect of these nodes", treeUnseenSub: "Removing them changes neither damage nor defence in PoB — usually a mechanic PoB does not model (warcry speed, Rage on hit, enemy effects). Check before removing.",
    treeAttributes: "Attribute nodes", treeAttributesSub: "Their worth is gem and item requirements, which PoB does not turn into damage. See the attributes on the Overview before removing.",
    pointsN: (n) => `${n} pts`, treeIntro: (n) => `Allocated main-tree nodes: ${n}. The goal is switched at the top (damage / balanced / defence).`,
    esRecoveryNote: "energy shield: recharge discounted by its delay, regen, leech",
    dpsMinions: "Minion army DPS", minionsNote: (n, per) => `${n} active × ${per} each`,
    lifeAndEs: "Life + energy shield", lifeEsNote: "life + energy shield",
    dmgFull_Physical: "Physical", dmgFull_Fire: "Fire", dmgFull_Cold: "Cold", dmgFull_Lightning: "Lightning", dmgFull_Chaos: "Chaos",
    hitsNote: "Higher is more dangerous. Under the percentage: how many such hits in a row kill you. 100% and above kills from full life in one hit. Bosses hit many times harder than ordinary monsters. Hover a number for the largest hit you survive.",
    cmpVersus: "Against a reference build", cmpItem: "Item against equipped",
    refTitle: "Compare with a reference", refSub: "A reference is someone's finished build (e.g. from a guide) with its gear. I show how far your characteristics are from it and what each of its items would do in your build.",
    refBuild: "Reference build", pickRef: "— pick a build —", refNone: "Add a reference build with “+ add build” on the left.",
    refLoading: "Loading the reference and computing…", refStats: "Characteristics",
    refStatsSub: (a, b) => `Each build is computed with its own profile against a level 79 monster. Main skill: yours “${a}”, reference “${b}”.`,
    refSkillDiffers: "The main skills differ — DPS compares only roughly, defence compares fully.",
    mine: "My build", diffMine: "Me vs them", now: "Now", change: "Change", withTheirGear: "With their gear",
    withCandidate: "With candidate",
    grp_offence: "Offence", grp_defence: "Defence", grp_resist: "Resistances", grp_hits: "Survivable hit",
    grp_attributes: "Attributes", grp_other: "Other",
    st_dps: "DPS", st_hitChance: "Hit chance", st_critChance: "Crit chance", st_speed: "Uses per second",
    st_life: "Life", st_es: "Energy shield", st_mana: "Mana", st_ehp: "EHP", st_armour: "Armour",
    st_evasion: "Evasion", st_res_Fire: "Fire", st_res_Cold: "Cold", st_res_Lightning: "Lightning", st_res_Chaos: "Chaos",
    st_hit_Physical: "physical", st_hit_Fire: "fire", st_hit_Cold: "cold", st_hit_Lightning: "lightning", st_hit_Chaos: "chaos",
    st_Str: "Strength", st_Dex: "Dexterity", st_Int: "Intelligence", st_spiritFree: "Free spirit", st_moveSpeed: "Movement speed",
    st_recovery: "Recovery in combat, /s",
    refItems: "The reference's items in your build", refItemsSub: "Each item of the reference tried in your build on its own (with your tree and gems).",
    ifWear: "If worn", refEmpty: "empty in the reference", cannotEquip: "PoB cannot equip it", wrongWeapon: "weapon does not fit the main skill",
    details: "details", refAllGear: "All the reference's gear at once", refAllGearSub: "Your build wearing every item of the reference together (slots they leave empty are empty too).",
    step1: "1. What to replace", step2: "2. Candidate", equippedNow: "Equipped now:", slotEmpty: "The slot is empty",
    fromRef: (n) => `take from reference “${n}”`, loadedFromRef: (n) => `Item taken from reference “${n}”.`,
    breakevenHelp: "Paste a mod line of the candidate: I compute how low it can roll and still be no worse than the equipped item. Handy when buying.",
    vBetter: "Better than equipped", vWorse: "Worse than equipped", vSame: "About the same",
    vMixed: (d, h) => `Mixed: damage ${d}, defence down to ${h}`,
    addToPob: "add to PoB's calculation", searching: "searching…", pobReads: "PoB will read this mechanic as:", addThis: "Add",
    orSimilar: "or a similar mod:", similarMods: "PoB does not read this line directly. Similar mods PoB does calculate:",
    orSearch: "or search for the mod:", addHint: "The correction goes to the profile unconfirmed with 100% uptime — adjust numbers and uptime on the Profile tab.",
    corrAdded: (m) => `Added to the profile: “${m}”. Recalculated.`,
    aiOn: (m) => `AI: ${m}`, aiOff: "AI not configured",
    mainSkill: "Main skill", goal: "Goal", mode_damage: "damage", mode_balanced: "balanced", mode_defence: "defence",
    tab_overview: "Overview", tab_damage: "Damage", tab_gear: "Gear", tab_compare: "Compare",
    tab_mechanics: "Mechanics", tab_profile: "Profile", tab_assistant: "Assistant",
    pickBuild: "Pick a build on the left",
    pickBuildHint: "Press “+ add build” on the left and paste a PoB code or a pobb.in link. Builds saved in Path of Building itself appear in the list on their own.",
    opening: "Opening the build in Path of Building…", openFailed: "Could not open the build", error: "Error",
    level: (n) => `level ${n}`,
    calcReport: "Computing the report (~5 s)…",
    dps: "DPS", life: "Life", hitChance: "Hit chance", recovery: "Recovery", perSec: " /s", whileAttacking: "while attacking",
    dpsRangeNote: "no enemy debuffs … all of them",
    hitsTitle: "How much a monster hit takes",
    hitsSub: (p, ph, ch) => `Share of your pool (life + energy shield) one heavy hit of an ordinary level ${p.enemy_level} monster takes (base ${ph}, chaos ${ch}). Hard map: monsters deal +${p.damage_pct}% damage and +${p.crit_bonus}% crit bonus.`,
    hitNormal: "normal hit", hitCrit: "crit", hitJuiced: "crit on a hard map",
    issuesTitle: "What is broken and where the gaps are", issuesSub: "“Broken” means it does not work in game although PoB counts it.",
    lvl_must: "broken", lvl_priority: "main", lvl_warn: "note",
    supportsAtRisk: "One of these supports is disabled in game — its cost if it is this one:",
    pathTitle: "Upgrade path", pathSub: "Each step is recomputed after the previous ones. One mod ≈ one average affix.",
    noEffect: "barely any effect",
    m_dps: "DPS", m_ehp: "EHP (with avoidance)", m_phys: "phys hit", m_fire: "fire", m_cold: "cold", m_lightning: "lightning", m_chaos: "chaos hit", m_recovery: "recovery",
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
    noQuestions: "No general questions for this build — it has neither Rage nor mana costs. Add mechanic corrections below.",
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
let BUILD_BASES = [], BUILD_ITEMS = [];  // item bases / full item names of the open build
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
// mod prefixes the game prints before the stat text (official wording from GGG's trade data)
const MOD_PREFIX_RU = { "Bonded: ": "Связаны: " };

function trMod(line) {
  if (LANG === "en" || !line) return line;
  return line.split(" / ").map((part) => {
    const prefix = Object.keys(MOD_PREFIX_RU).find((p) => part.startsWith(p));
    const body = prefix ? part.slice(prefix.length) : part;
    const tpl = GAME.stats[statKey(part)] || GAME.stats[statKey(body)];
    const done = tpl && fillTemplate(tpl, GAME.stats[statKey(part)] ? part : body);
    if (!done) return part;
    return GAME.stats[statKey(part)] || !prefix ? done : MOD_PREFIX_RU[prefix] + done;
  }).join(" / ");
}

function trName(name) {
  if (LANG === "en" || !name) return name;
  return GAME.names[name] || CLASS_RU[name] || name;
}

// "Random Name, Base Type" for rares / "Unique Name, Base Type" for uniques / "Prefix Base of Suffix" for magic
// items. Random rare names and magic affix names have several Russian variants in the game's word lists, so they
// cannot be recovered from English exactly: those items are shown by their base.
function trItem(name) {
  if (LANG === "en" || !name) return name;
  const parts = name.split(", ");
  if (parts.length === 2) {
    const [first, base] = parts;
    return GAME.names[first] ? `${GAME.names[first]}, ${trName(base)}` : trName(base);
  }
  if (GAME.names[name]) return GAME.names[name];
  const base = BUILD_BASES.find((b) => name.includes(b));
  return base ? GAME.names[base] : name;
}

function setBuildNames(build) {
  const names = new Set();
  for (const g of build.groups || []) g.skills.forEach((s) => names.add(s));
  for (const g of build.gems || []) names.add(g);
  for (const it of build.items || []) { it.name.split(", ").forEach((p) => names.add(p)); names.add(it.baseName); }
  BUILD_NAMES = [...names].filter((n) => n && GAME.names[n]).sort((a, b) => b.length - a.length);
  BUILD_BASES = [...new Set((build.items || []).map((it) => it.baseName))]
    .filter((n) => n && GAME.names[n]).sort((a, b) => b.length - a.length);
  // full item names as the server writes them into sentences: "Rare Name, Base" → the base alone in Russian
  BUILD_ITEMS = (build.items || []).map((it) => it.name).filter((n) => n && n.includes(", "))
    .sort((a, b) => b.length - a.length);
}

const SUPPORT_COLOR_RU = { Strength: "красных", Dexterity: "зелёных", Intelligence: "синих" };

// server-made sentences: translate «quoted mods», support-gem counts and names from the open build
function trFree(text) {
  if (LANG === "en" || !text) return text;
  let s = text.replace(/«([^»]+)»/g, (_, inner) =>
    `«${SLOT_RU[inner] !== undefined ? slotName(inner) : GAME.names[inner] ? GAME.names[inner] : trMod(inner)}»`);
  for (const n of BUILD_ITEMS) s = s.split(n).join(trItem(n));
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
  [/Druidic Prowess/g, "Друидизм"],
  [/ ?(?:стат )?[a-z0-9%+]+(?:_[a-z0-9%+]+){2,}/g, ""],  // internal stat ids: no use to a player
  [/Custom Modifiers/g, "пользовательские модификаторы"],
  [/\((\d+) (Str|Dex|Int)\)/g, (_, n, a) => `(${n} ${ATTR_GEN_RU[a]})`],
  // slot lists the server writes plainly: "держат предметы: Gloves, Belt"
  [/(держат предметы: )([^;]+)/g, (_, head, list) => head + list.split(", ").map((x) => (SLOT_RU[x] ? SLOT_RU[x] : x)).join(", ")],
  // currency: Divine Orb / Exalted Orb in the client's words, shortened
  [/(\d) div\b/g, "$1 бож."],
  [/(\d|<1) ex\b/g, "$1 возв."],
];

// "обычный ролл: MOD (нужен уровень предмета N+)" / "эссенция NAME: MOD — price" / "desecration: MOD"
function trSource(src) {
  if (LANG === "en") return src;
  let m = src.match(/^обычный ролл: (.+?)( \(нужен уровень предмета \d+\+\))?$/);
  if (m) return `обычный ролл: ${trMod(m[1])}${m[2] || ""}`;
  m = src.match(/^эссенция (.+?): (.+?)( — .+)?$/);
  if (m) return `эссенция ${trName(m[1])}: ${trMod(m[2])}${trFree(m[3] || "")}`;
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
  if (POB_LABELS_RU[label]) return POB_LABELS_RU[label];
  let m = label.match(/^Is the enemy (.+?)\??$/);
  if (m) return `Враг ${STATE_RU[m[1]] || m[1]}?`;
  m = label.match(/^Do you have (.+?)\?$/);
  if (m) return `Есть ${BUFF_RU[m[1]] || m[1]}?`;
  m = label.match(/^Act (\d+): (.+)$/);
  if (m) return `Акт ${m[1]}: ${trName(m[2])}`;
  m = label.match(/^Interlude (\d+): (.+)$/);
  if (m) return `Интерлюдия ${m[1]}: ${trName(m[2])}`;
  return label;
}
