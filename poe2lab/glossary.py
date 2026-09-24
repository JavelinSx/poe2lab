"""A beginner's glossary in our own words: what a term is, when it matters to you, and how it links to its neighbours
(chill and freeze are two effects of the same cold damage...). Checked against the game's own definitions; shorter,
and written for someone in their first league. It replaces the game's hover texts where it has the term, so the
player's game files are not needed for them.

Text markup: "[Id|shown words]" links another term (the page and the popups open it)."""

GROUPS = [
    ("damage", {"ru": "Урон: как он считается", "en": "Damage: how it adds up"}),
    ("ailments", {"ru": "Состояния врагов", "en": "Ailments"}),
    ("defence", {"ru": "Защита", "en": "Defences"}),
    ("resources", {"ru": "Ресурсы", "en": "Resources"}),
    ("crafting", {"ru": "Крафт", "en": "Crafting"}),
    ("basics", {"ru": "Основы предметов", "en": "Item basics"}),
]

# id (the game's keyword id where it has one, so its mentions link here), group, names, text
ENTRIES = [
    # ---------- damage ----------
    ("DamageFormula", "damage", {"ru": "Как складывается урон", "en": "How damage adds up"}, {
        "ru": "Урон удара считается по шагам:\n"
              "1. Основа: урон оружия плюс [AddedDamage|добавленный урон] (у чар — урон самого камня).\n"
              "2. Для атак — множитель скилла «[AttackMultiplier|урон атаки: N% от базового]».\n"
              "3. Все «увеличения» складываются в одно число и умножают: ×(1 + сумма). См. "
              "[IncreasedMore|увеличение и «больше»].\n"
              "4. Каждое «больше» умножает отдельно.\n"
              "5. Крит, затем [Resistances|сопротивление] врага.\n"
              "Отсюда главное: сильнее всего помогает мод, который двигает шаг, где у тебя пока мало. Точно для "
              "твоего билда это считает вкладка «Урон» → «Куда вкладываться».",
        "en": "A hit's damage is worked out in steps:\n"
              "1. The base: the weapon's damage plus [AddedDamage|added damage] (for spells, the gem's own damage).\n"
              "2. For attacks, the skill's \"[AttackMultiplier|attack damage: N% of base]\".\n"
              "3. All \"increased\" add up into one number and multiply: ×(1 + total). See "
              "[IncreasedMore|increased and more].\n"
              "4. Each \"more\" multiplies on its own.\n"
              "5. Crits, then the enemy's [Resistances|resistance].\n"
              "So the mod that moves the step you have least of helps most. The Damage tab → \"Where to invest\" "
              "works it out for your build exactly."}),
    ("AddedDamage", "damage", {"ru": "Добавленный урон («добавляет от X до Y»)", "en": "Added damage (\"adds X to Y\")"}, {
        "ru": "Прибавляет числа к основе урона. Дальше их умножают все проценты билда, скорость атаки и множитель "
              "скилла. На оружии добавляется к урону этого оружия, на кольцах, перчатках, амулете — ко всем атакам "
              "(см. [LocalGlobal|локальные и глобальные моды]).\n"
              "Когда важно: чем больше у тебя уже набрано «увеличений», тем ценнее добавленный урон. Стихийный "
              "добавленный урон ещё и накладывает состояния: больше огня — чаще [Ignite|поджог].",
        "en": "Adds numbers to the base damage. Every percentage of the build, attack speed and the skill's multiplier "
              "then scale them. On a weapon it adds to that weapon's damage; on rings, gloves or an amulet to all "
              "attacks (see [LocalGlobal|local and global mods]).\n"
              "When it matters: the more \"increased\" you already have, the more added damage is worth. Elemental "
              "added damage also applies ailments: more fire, more [Ignite]."}),
    ("IncreasedMore", "damage", {"ru": "Увеличение и «больше»", "en": "Increased and more"}, {
        "ru": "Два разных вида процентов.\n"
              "• «Увеличение» (и «снижение») подходящего урона складываются в одну сумму. Если уже набрано 150%, "
              "ещё +30% даёт ×2,8 вместо ×2,5 — прибавка всего около 12%.\n"
              "• «Больше» (и «меньше») умножает отдельно: на 30% больше — это ровно +30% урона, сколько бы ни было "
              "остального. Такие моды реже (часто в поддержках) и ценнее.\n"
              "Внимание: «увеличение урона от стихий от умений атак» усиливает только стихийную часть и только "
              "атаки. Нет стихийного урона — мод даёт ноль.",
        "en": "Two different kinds of percentages.\n"
              "• \"Increased\" (and \"reduced\") of matching damage add up into one total. With 150% already, "
              "another 30% makes ×2.8 instead of ×2.5: only about 12% more.\n"
              "• \"More\" (and \"less\") multiplies on its own: 30% more is exactly 30% more damage whatever else "
              "you have. Such mods are rarer (often on supports) and worth more.\n"
              "Note: \"increased elemental damage with attacks\" boosts only the elemental part and only attacks. "
              "No elemental damage: the mod gives nothing."}),
    ("AttackMultiplier", "damage", {"ru": "Урон атаки «N% от базового»", "en": "Attack damage \"N% of base\""}, {
        "ru": "В описании атакующего скилла написано «Урон атаки: N% от базового». Это множитель ко всему урону "
              "оружия, включая [AddedDamage|добавленный]. У сильного медленного удара он высокий — каждый пункт "
              "добавленного урона стоит больше. Чары урон оружия не используют: моды на урон оружия им не помогают.",
        "en": "An attack skill says \"Attack Damage: N% of base\". It multiplies all the weapon's damage, "
              "[AddedDamage|added] included. A slow heavy attack has a high one: each point of added damage is worth "
              "more. Spells do not use weapon damage: weapon damage mods do not help them."}),
    ("LocalGlobal", "damage", {"ru": "Локальные и глобальные моды", "en": "Local and global mods"}, {
        "ru": "Моды оружия и брони на её собственные числа — «локальные»: «% увеличение физического урона» и "
              "«добавляет X–Y урона» на оружии меняют только это оружие, «% увеличение брони» на нагруднике — только "
              "его броню. Такой же текст на кольце или амулете — «глобальный» и действует на всё.",
        "en": "Mods of a weapon or armour piece on its own numbers are local: \"% increased Physical Damage\" and "
              "\"adds X–Y damage\" on a weapon change only that weapon, \"% increased Armour\" on a body armour only "
              "its armour. The same text on a ring or amulet is global and applies to everything."}),
    ("Gain", "damage", {"ru": "Дополнительный урон в виде X", "en": "Damage gained as extra X"}, {
        "ru": "«Получает N% физического урона в виде дополнительного урона огнём»: к удару добавляется новый огонь, "
              "равный N% физического. Физический урон при этом не убывает. Новый огонь усиливается только модами на "
              "огонь и стихии, а не на физический урон.",
        "en": "\"Gain N% of physical damage as extra fire damage\": the hit gets new fire damage equal to N% of the "
              "physical. The physical damage stays. The new fire scales only with fire and elemental mods, not "
              "physical ones."}),
    ("Penetration", "damage", {"ru": "Пробивание сопротивлений", "en": "Resistance penetration"}, {
        "ru": "Твои удары считают [Resistances|сопротивление] врага ниже на указанное число, но не ниже нуля. "
              "Действует только на удары — не на [Ignite|поджог] и [Poison|яд]. [Exposure|Восприимчивость], наоборот, "
              "снижает само сопротивление — для всего урона и даже ниже нуля.",
        "en": "Your hits treat the enemy's [Resistances|resistance] as lower by the stated amount, down to zero. It "
              "works on hits only, not on [Ignite] or [Poison]. [Exposure] instead lowers the resistance itself, for "
              "all damage and even below zero."}),
    ("Resistances", "damage", {"ru": "Сопротивления", "en": "Resistances"}, {
        "ru": "Снижают урон своего типа: огонь, холод, молния (это стихии) и хаос. У тебя максимум — 75% (выше не "
              "работает, пока не поднят сам максимум). По ходу кампании сопротивления получают штраф — поэтому "
              "поздним актам и картам нужно больше сопротивлений на шмоте. Вкладка «Обзор» показывает, где у тебя "
              "дыра.",
        "en": "Reduce damage of their type: fire, cold, lightning (the elements) and chaos. Yours cap at 75% (more "
              "does nothing until the maximum itself rises). The campaign adds a resistance penalty as you go, so "
              "late acts and maps need more resistances on gear. The Overview tab shows where yours are short."}),
    # ---------- ailments ----------
    ("ElementalColdChain", "ailments", {"ru": "Холод: охлаждение и заморозка", "en": "Cold: chill and freeze"}, {
        "ru": "Урон холодом делает с врагом две разные вещи сразу.\n"
              "• [Chill|Охлаждение] — замедление. Наступает от любого заметного удара холодом, шанс не нужен. "
              "Держится, пока бьёшь.\n"
              "• [Freeze|Заморозка] — полная остановка. Каждый удар холодом наполняет шкалу заморозки; когда она "
              "полная, враг стоит на месте 4 секунды.\n"
              "Как пользоваться: частые удары холодом держат толпу медленной — это защита. Крупные удары быстрее "
              "наполняют шкалу. Заморозка редкого монстра или босса — это окно, в которое бьёшь самым сильным. "
              "Некоторые скиллы бьют сильнее по замороженным или «разбивают» их — тогда холод работает как подготовка "
              "к удару. Шкала у боссов больше — см. [AilmentThreshold|порог состояний].",
        "en": "Cold damage does two different things at once.\n"
              "• [Chill] slows. Any sizeable cold hit applies it, no chance needed. It lasts while you keep hitting.\n"
              "• [Freeze] stops the enemy. Each cold hit fills a freeze bar; when it is full, the enemy stands still "
              "for 4 seconds.\n"
              "How to use it: frequent cold hits keep a pack slow, which is defence. Big hits fill the bar faster. "
              "Freezing a rare monster or a boss opens a window for your strongest hit. Some skills deal more to "
              "frozen enemies or shatter them: then cold is the set-up for that hit. Bosses have a bigger bar — see "
              "[AilmentThreshold|ailment threshold]."}),
    ("Chill", "ailments", {"ru": "Охлаждение", "en": "Chill"}, {
        "ru": "Замедляет врага (движение, атаки, чары) на 30–50%. Накладывается любым ударом холодом без всякого "
              "шанса, но удар, который замедлил бы меньше чем на 30%, не охлаждает — слабые удары по сильным врагам "
              "не работают. Редкие и уникальные враги замедляются слабее.\n"
              "Когда важно: если бьёшь холодом — это бесплатная защита. Не путай с [Freeze|заморозкой]: охлаждение "
              "замедляет, заморозка останавливает. См. [ElementalColdChain|холод целиком].",
        "en": "Slows the enemy (moving, attacking, casting) by 30–50%. Any cold hit applies it without a chance, but "
              "a hit that would slow by less than 30% does not chill: weak hits on tough enemies fail. Rare and unique "
              "enemies are slowed less.\n"
              "When it matters: if you deal cold damage, it is free defence. Not the same as [Freeze]: chill slows, "
              "freeze stops. See [ElementalColdChain|cold as a whole]."}),
    ("Freeze", "ailments", {"ru": "Заморозка", "en": "Freeze"}, {
        "ru": "Враг не двигается и ничего не делает 4 секунды. Не срабатывает «по шансу»: урон холодом копит шкалу "
              "заморозки, и когда она заполнена — враг заморожен. Чем больше урон удара относительно "
              "[AilmentThreshold|порога] врага, тем быстрее растёт шкала.\n"
              "Когда важно: против редких монстров и боссов — это время бить без ответа. Моды «увеличение накопления "
              "заморозки» ускоряют шкалу. Замороженный не может [Block|блокировать]. См. "
              "[PrimedFreeze|готовность к заморозке] и [ElementalColdChain|холод целиком].",
        "en": "The enemy cannot move or act for 4 seconds. It is not a chance: cold damage fills a freeze bar, and a "
              "full bar freezes. The bigger the hit compared with the enemy's [AilmentThreshold|threshold], the faster "
              "the bar fills.\n"
              "When it matters: against rares and bosses it is time to hit freely. \"Increased Freeze Buildup\" mods "
              "fill the bar faster. A frozen target cannot [Block]. See [PrimedFreeze|primed for freeze] and "
              "[ElementalColdChain|cold as a whole]."}),
    ("PrimedFreeze", "ailments", {"ru": "Готовность к заморозке", "en": "Primed for Freeze"}, {
        "ru": "Промежуточная стадия [Freeze|заморозки]: шкала заполнена на 40% у обычных врагов, на 50% у "
              "магических, 60% у редких и 70% у уникальных. Некоторые скиллы и поддержки срабатывают уже на ней — "
              "не нужно доводить до полной заморозки.\n"
              "Когда важно: если в описании скилла есть «готовность к заморозке».",
        "en": "The step before [Freeze]: the bar is 40% full on normal enemies, 50% on magic, 60% on rare and 70% on "
              "unique ones. Some skills and supports trigger on it already, without a full freeze.\n"
              "When it matters: when a skill mentions \"primed for freeze\"."}),
    ("Ignite", "ailments", {"ru": "Поджог", "en": "Ignite"}, {
        "ru": "Горение: урон огнём со временем, 4 секунды. За секунду наносит 20% огненного урона удара, который "
              "поджёг. Шанс поджечь зависит от огненного урона удара — чем сильнее удар огнём, тем чаще поджигает "
              "(это копит [Flammability|горючесть] на враге).\n"
              "Когда важно: если бьёшь огнём крупными ударами — поджог добавляет урон сверху. "
              "[Shock|Шок] на враге усиливает и поджог.",
        "en": "Burning: fire damage over time for 4 seconds. Each second it deals 20% of the fire damage of the hit "
              "that ignited. The chance to ignite depends on the hit's fire damage: stronger fire hits ignite more "
              "often (they build [Flammability] on the enemy).\n"
              "When it matters: with big fire hits ignite adds damage on top. [Shock] on the enemy boosts ignite too."}),
    ("Flammability", "ailments", {"ru": "Горючесть", "en": "Flammability"}, {
        "ru": "Не состояние, а «шанс поджога», который копится на враге от ударов огнём. Чем больше огненный урон "
              "удара относительно [AilmentThreshold|порога] врага, тем выше горючесть и шанс [Ignite|поджога].",
        "en": "Not an ailment but the chance to [Ignite] that fire hits build on the enemy. The more fire damage "
              "against the enemy's [AilmentThreshold|threshold], the higher it gets."}),
    ("Shock", "ailments", {"ru": "Шок", "en": "Shock"}, {
        "ru": "Враг получает на 20% больше урона — от всех источников, 8 секунд. Шанс зависит от урона молнией: 1% "
              "за каждые 4% [AilmentThreshold|порога] врага, снятые ударом.\n"
              "Когда важно: если бьёшь молнией, шок — это прибавка ко всему урону группы, включая "
              "[Ignite|поджог] и [Poison|яд]. Не путай с [Electrocute|электризацией] — та останавливает врага.",
        "en": "The enemy takes 20% more damage from everything, for 8 seconds. The chance comes from lightning "
              "damage: 1% per 4% of the enemy's [AilmentThreshold|threshold] the hit deals.\n"
              "When it matters: with lightning damage shock boosts all damage the enemy takes, [Ignite] and [Poison] "
              "included. Not the same as [Electrocute], which stops the enemy."}),
    ("Electrocute", "ailments", {"ru": "Электризация", "en": "Electrocute"}, {
        "ru": "Молниевый аналог [Freeze|заморозки]: враг не действует 5 секунд, когда заполнится шкала. Копят её "
              "только особые скиллы и эффекты, а не любой урон молнией.",
        "en": "The lightning twin of [Freeze]: the enemy cannot act for 5 seconds once its bar fills. Only specific "
              "skills and effects fill it, not every lightning hit."}),
    ("Bleeding", "ailments", {"ru": "Кровотечение", "en": "Bleeding"}, {
        "ru": "Физический урон со временем, 5 секунд. Идёт мимо [EnergyShield|энергощита] прямо по здоровью. Если "
              "враг двигается — урон вдвое больше. Само не накладывается: нужен явный «шанс вызвать "
              "кровотечение» в скиллах, поддержках или пассивках.\n"
              "Когда важно: физическим билдам с источником кровотечения. [Aggravate|Усугубление] делает его всегда "
              "двойным.",
        "en": "Physical damage over time for 5 seconds. It bypasses [EnergyShield] and hits life directly. Double "
              "damage while the enemy moves. It never happens by itself: it needs an explicit \"chance to cause "
              "bleeding\" from skills, supports or passives.\n"
              "When it matters: physical builds with a bleed source. [Aggravate|Aggravating] makes it always double."}),
    ("Aggravate", "ailments", {"ru": "Усугублённое кровотечение", "en": "Aggravated Bleeding"}, {
        "ru": "[Bleeding|Кровотечение], которое всегда считается «враг движется» — то есть наносит двойной урон, "
              "даже если враг стоит.",
        "en": "[Bleeding] that always counts the enemy as moving, so it deals double damage even on a standing "
              "enemy."}),
    ("Poison", "ailments", {"ru": "Отравление", "en": "Poison"}, {
        "ru": "Урон хаосом со временем, 2 секунды: за секунду 20% физического и хаосного урона удара. Идёт мимо "
              "[EnergyShield|энергощита]. Как и [Bleeding|кровотечение], само не накладывается — нужен явный шанс "
              "отравить.\n"
              "Когда важно: быстрые физические или хаосные удары с шансом отравить.",
        "en": "Chaos damage over time for 2 seconds: each second 20% of the hit's physical and chaos damage. It "
              "bypasses [EnergyShield]. Like [Bleeding], it needs an explicit chance to poison.\n"
              "When it matters: fast physical or chaos hits with a poison chance."}),
    ("AilmentThreshold", "ailments", {"ru": "Порог состояний", "en": "Ailment Threshold"}, {
        "ru": "«Запас прочности» врага против [Chill|охлаждения], [Freeze|заморозки], [Shock|шока], "
              "[Ignite|поджога]. Шанс и накопление считаются от урона удара относительно этого порога: у боссов он "
              "большой, поэтому нужны крупные удары. У тебя самого порог — половина здоровья.",
        "en": "The enemy's resistance to [Chill], [Freeze], [Shock] and [Ignite]. Chance and build-up come from the "
              "hit's damage compared with it: bosses have a big one, so they need big hits. Yours is half your "
              "life."}),
    ("Stun", "ailments", {"ru": "Оглушение", "en": "Stun"}, {
        "ru": "Прерывает действие врага. Лёгкое — на долю секунды, по шансу от урона удара. "
              "[HeavyStun|Тяжёлое] — на несколько секунд, когда полностью наполнится шкала оглушения. Физический "
              "урон и ближний бой оглушают в полтора раза лучше (вместе — в 2,25).\n"
              "Когда важно: билдам ближнего боя с тяжёлыми ударами — оглушение и есть их защита.",
        "en": "Interrupts the enemy. A light stun lasts a fraction of a second, by chance from the hit's damage. A "
              "[HeavyStun|heavy] one lasts several seconds when the stun bar fills. Physical damage and melee each "
              "stun 50% better (2.25x together).\n"
              "When it matters: melee builds with heavy hits: stun is their defence."}),
    ("HeavyStun", "ailments", {"ru": "Тяжёлое оглушение", "en": "Heavy Stun"}, {
        "ru": "Полная шкала [Stun|оглушения]: враг не действует несколько секунд. Многие скиллы бьют сильнее по "
              "тяжело оглушённым.",
        "en": "A full [Stun] bar: the enemy cannot act for several seconds. Many skills hit harder on heavily "
              "stunned enemies."}),
    ("ArmourBreak", "ailments", {"ru": "Разрушение брони", "en": "Armour Break"}, {
        "ru": "Снижает [Armour|броню] врага. Когда броня падает до нуля, она «полностью разрушена» на 12 секунд: "
              "враг не защищён бронёй и получает на 20% больше физического урона.\n"
              "Когда важно: физическим билдам — сначала ломаешь броню, потом бьёшь.",
        "en": "Lowers the enemy's [Armour]. At zero it is fully broken for 12 seconds: no armour, and 20% more "
              "physical damage taken.\n"
              "When it matters: physical builds: break the armour, then hit."}),
    ("Exposure", "ailments", {"ru": "Восприимчивость", "en": "Exposure"}, {
        "ru": "Снижает сопротивление врага стихиям на 20% на 4 секунды (у редких и уникальных эффект слабее). "
              "Даже ниже нуля.\n"
              "Когда важно: если бьёшь огнём, холодом или молнией и есть скилл, который её накладывает.",
        "en": "Lowers the enemy's elemental resistances by 20% for 4 seconds (less on rares and uniques), even below "
              "zero.\n"
              "When it matters: with fire, cold or lightning damage and a skill that applies it."}),
    # ---------- defence ----------
    ("Armour", "defence", {"ru": "Броня", "en": "Armour"}, {
        "ru": "Снижает урон от физических ударов. Лучше всего против мелких ударов, против огромных — слабее. "
              "Против стихий и хаоса сама не работает (только с особыми модами). Враги могут её "
              "[ArmourBreak|разрушить].\n"
              "Когда важно: билдам на силу, ближний бой. Для защиты от стихий нужны сопротивления.",
        "en": "Reduces damage from physical hits. Best against small hits, weaker against huge ones. Does nothing "
              "against elements and chaos by itself (only with specific mods). Can be [ArmourBreak|broken].\n"
              "When it matters: strength and melee builds. Resistances guard against elements."}),
    ("Evasion", "defence", {"ru": "Уклонение", "en": "Evasion"}, {
        "ru": "Шанс, что удар вообще не попадёт — ни урона, ни эффектов. Шанс зависит от меткости нападающего. "
              "Не спасает от урона со временем и эффектов на земле — это не удары.\n"
              "Когда важно: билдам на ловкость. Хорошо сочетается с [EnergyShield|энергощитом].",
        "en": "A chance that a hit misses completely: no damage, no effects. It depends on the attacker's accuracy. "
              "Does not help against damage over time or ground effects: they are not hits.\n"
              "When it matters: dexterity builds. Pairs well with [EnergyShield]."}),
    ("EnergyShield", "defence", {"ru": "Энергетический щит", "en": "Energy Shield"}, {
        "ru": "Второй запас здоровья поверх обычного: урон сначала снимает щит. Быстро восстанавливается целиком, "
              "если какое-то время не получать урон. Хаос снимает его вдвое быстрее, а [Bleeding|кровотечение] и "
              "[Poison|яд] бьют мимо щита прямо по здоровью.\n"
              "Когда важно: билдам на интеллект. Опасно против хаоса и ядов.",
        "en": "A second pool on top of life: damage takes it first. It recharges fully and fast after a short time "
              "without losing it. Chaos removes it twice as fast; [Bleeding] and [Poison] go past it to life.\n"
              "When it matters: intelligence builds. Beware chaos and poison."}),
    ("Block", "defence", {"ru": "Блок", "en": "Block"}, {
        "ru": "Шанс полностью отменить урон удара. [Stun|Оглушение] от удара всё равно приходит. Нельзя блокировать "
              "оглушённым или [Freeze|замороженным]. Некоторые удары боссов не блокируются — они светятся красным "
              "перед ударом.\n"
              "Когда важно: со щитом или баклером.",
        "en": "A chance to cancel a hit's damage entirely. The hit's [Stun] still lands. You cannot block while "
              "stunned or [Freeze|frozen]. Some boss attacks cannot be blocked: they glow red before landing.\n"
              "When it matters: with a shield or buckler."}),
    ("Thorns", "defence", {"ru": "Шипы", "en": "Thorns"}, {
        "ru": "Твой ответный урон тем, кто бьёт тебя в ближнем бою. Это не урон атаки и не чары — моды на атаки и "
              "чары его не усиливают.",
        "en": "Your damage back to whoever hits you in melee. Not attack or spell damage: attack and spell mods do "
              "not raise it."}),
    # ---------- resources ----------
    ("Charges", "resources", {"ru": "Заряды", "en": "Charges"}, {
        "ru": "Заряды выносливости, ярости и энергии — по 3 каждого, держатся 15 секунд. В PoE2 сами по себе ничего "
              "не дают: их тратят скиллы и пассивки ради сильного эффекта. Если ничего в билде их не тратит — не "
              "вкладывайся в их получение.",
        "en": "Endurance, frenzy and power charges, 3 of each, lasting 15 seconds. In PoE2 they do nothing by "
              "themselves: skills and passives spend them for a strong effect. If nothing in your build spends them, "
              "do not invest in gaining them."}),
    ("Rage", "resources", {"ru": "Свирепость", "en": "Rage"}, {
        "ru": "+1% к урону атак за каждое очко, максимум 30. Копится от ударов атаками (не чаще раза в полсекунды), "
              "быстро тает, если перестать бить или получать урон.\n"
              "Когда важно: воинам ближнего боя — это почти бесплатные +30% урона, пока ты в драке.",
        "en": "1% more attack damage per point, 30 at most. Attack hits build it (at most once per half second); it "
              "drains fast once you stop hitting or taking damage.\n"
              "When it matters: melee warriors: nearly free 30% more damage while fighting."}),
    ("Glory", "resources", {"ru": "Слава", "en": "Glory"}, {
        "ru": "Ресурс для особых мощных скиллов (знамёна и др.). Каждый такой скилл копит свою славу своим способом "
              "и тратит её при использовании. Без использования 15 секунд — начинает убывать.\n"
              "Когда важно: только если у тебя есть скилл, которому нужна слава.",
        "en": "The resource of some powerful skills (banners and others). Each such skill builds its own glory its "
              "own way and spends it on use. It drains after 15 seconds unused.\n"
              "When it matters: only with a skill that needs glory."}),
    # ---------- crafting ----------
    ("CurrencyGrades", "crafting", {"ru": "Обычные, большие и совершенные сферы",
                                    "en": "Regular, greater and perfect orbs"}, {
        "ru": "У сфер превращения, усиления, царей, возвышения и хаоса есть три вида. Большие не дают модов ниже "
              "35-го уровня (подтверждено журналом крафта poe2lab), совершенные — ниже 50-го (пока предварительно). Меньше слабых "
              "[Tier|тиров] — но дороже. На высоком уровне крафтят совершенными.",
        "en": "Transmutation, augmentation, regal, exalted and chaos orbs come in three grades. Greater ones add no "
              "mod below level 35, perfect ones none below 50 (the journal confirmed 35; 50 is tentative). Fewer weak "
              "[Tier|tiers], higher price. High-level crafting uses perfect ones."}),
    ("OrbTransmutation", "crafting", {"ru": "Сфера превращения", "en": "Orb of Transmutation"}, {
        "ru": "Белый предмет → синий (магический) с одним случайным модом. Начало любого крафта с нуля.",
        "en": "White item → blue (magic) with one random mod. The start of any craft from scratch."}),
    ("OrbAugmentation", "crafting", {"ru": "Сфера усиления", "en": "Orb of Augmentation"}, {
        "ru": "Добавляет второй мод синему предмету (у синего максимум 1 [Prefix|префикс] и 1 суффикс).",
        "en": "Adds a second mod to a magic item (magic items hold 1 [Prefix|prefix] and 1 suffix)."}),
    ("RegalOrb", "crafting", {"ru": "Сфера царей", "en": "Regal Orb"}, {
        "ru": "Синий предмет → жёлтый (редкий) плюс один новый мод. Дальше мод за модом добавляет "
              "[ExaltedOrb|сфера возвышения].",
        "en": "Magic item → rare, plus one new mod. After that [ExaltedOrb|exalted orbs] add mods one by one."}),
    ("ExaltedOrb", "crafting", {"ru": "Сфера возвышения", "en": "Exalted Orb"}, {
        "ru": "Добавляет редкому предмету один случайный мод, пока есть место (до 3 префиксов и 3 суффиксов). "
              "[Omen|Предзнаменования] могут направить мод на нужную сторону или дать сразу два.",
        "en": "Adds one random mod to a rare item while there is room (up to 3 prefixes and 3 suffixes). "
              "[Omen|Omens] can steer it to one side or add two at once."}),
    ("OrbAlchemy", "crafting", {"ru": "Сфера алхимии", "en": "Orb of Alchemy"}, {
        "ru": "Белый предмет → сразу редкий с четырьмя случайными модами. Быстро, но без контроля.",
        "en": "White item → rare with four random mods at once. Fast, but no control."}),
    ("ChaosOrb", "crafting", {"ru": "Сфера хаоса", "en": "Chaos Orb"}, {
        "ru": "Убирает случайный мод редкого предмета и добавляет новый случайный. «Перекрутить» одну позицию. "
              "Спамить хаос ради всей вещи — очень дорого.",
        "en": "Removes a random mod from a rare item and adds a new random one: a reroll of one slot. Spamming chaos "
              "for a whole item is very expensive."}),
    ("OrbAnnulment", "crafting", {"ru": "Сфера отмены", "en": "Orb of Annulment"}, {
        "ru": "Убирает случайный мод. Риск снять хороший; с предзнаменованием стороны — только префикс или только "
              "суффикс.",
        "en": "Removes a random mod. It may hit a good one; with a side omen, only a prefix or only a suffix."}),
    ("DivineOrb", "crafting", {"ru": "Божественная сфера", "en": "Divine Orb"}, {
        "ru": "Перебрасывает числа модов в пределах их [Tier|тиров] — сами моды не меняются. Ещё и главная «валюта "
              "цен» в торговле.",
        "en": "Rerolls the numbers of the mods within their [Tier|tiers]; the mods stay. Also the main price "
              "currency in trade."}),
    ("Essence", "crafting", {"ru": "Эссенция", "en": "Essence"}, {
        "ru": "Синий предмет → редкий с гарантированным модом (каким — написано на эссенции). Совершенные эссенции "
              "работают на уже редких вещах: убирают случайный мод и добавляют свой.\n"
              "Когда важно: самый надёжный способ получить нужный мод.",
        "en": "Magic item → rare with a guaranteed mod (named on the essence). Perfect essences work on rares: they "
              "remove a random mod and add theirs.\n"
              "When it matters: the surest way to get a wanted mod."}),
    ("Omen", "crafting", {"ru": "Предзнаменования", "en": "Omens"}, {
        "ru": "Лежат в инвентаре и меняют действие следующей подходящей сферы: только префиксы или только суффиксы "
              "(«левши»/«правши»), сразу два мода (великое возвышение), убрать самый слабый мод (оттачивание) и т.д. "
              "Тратятся при срабатывании.",
        "en": "Sit in your inventory and change the next matching orb: prefixes only or suffixes only "
              "(sinistral/dextral), two mods at once (greater exaltation), remove the weakest mod (whittling), and "
              "more. Used up when they fire."}),
    ("Abyssalify", "crafting", {"ru": "Очернение (кости)", "en": "Desecration (bones)"}, {
        "ru": "Кости добавляют редкому предмету скрытый очернённый мод: челюсть — оружию, ребро — броне, ключица — "
              "бижутерии. Раскрывается у Колодца душ: выбираешь из нескольких вариантов. Если места нет — случайный "
              "мод уходит. Второй раз очернить нельзя.",
        "en": "Bones add a hidden desecrated mod to a rare item: jawbone for weapons, rib for armour, collarbone for "
              "jewellery. It is revealed at the Well of Souls, picking from a few options. With no room, a random mod "
              "goes. An item can be desecrated once."}),
    ("Fracture", "crafting", {"ru": "Раскол", "en": "Fracture"}, {
        "ru": "Раскалывающая сфера закрепляет случайный мод редкого предмета с 4+ модами навсегда — его уже не "
              "убрать и не изменить. Дальше можно перекручивать остальное.",
        "en": "A Fracturing Orb locks a random mod of a rare item with 4+ mods for good: it can never be removed or "
              "changed. The rest can then be reworked."}),
    # ---------- basics ----------
    ("Prefix", "basics", {"ru": "Префиксы и суффиксы", "en": "Prefixes and suffixes"}, {
        "ru": "Моды делятся на две «стороны». У синего предмета — 1 префикс и 1 суффикс, у редкого — до 3 и 3. "
              "Здоровье, броня, урон обычно префиксы; сопротивления, характеристики, скорость атаки — суффиксы. Если сторона "
              "полна, туда больше ничего не добавить.",
        "en": "Mods come in two sides. Magic items hold 1 prefix and 1 suffix, rares up to 3 and 3. Life, armour and "
              "damage are usually prefixes; resistances, attributes and attack speed suffixes. A full side takes no more."}),
    ("Tier", "basics", {"ru": "Тир мода", "en": "Mod tier"}, {
        "ru": "Один и тот же мод бывает разной силы — это тиры. Тир 1 — лучший. Сильные тиры требуют высокого "
              "[ItemLevel|уровня предмета]. По журналу крафта poe2lab: на броне и бижутерии все доступные тиры "
              "выпадают одинаково часто, на оружии верхние — реже.",
        "en": "The same mod comes in strengths: tiers. Tier 1 is the best. Strong tiers need a high "
              "[ItemLevel|item level]. By poe2lab's craft journal, on armour and jewellery every available tier rolls "
              "equally often; on weapons the top ones are rarer."}),
    ("ItemLevel", "basics", {"ru": "Уровень предмета", "en": "Item level"}, {
        "ru": "Уровень, на котором предмет выпал. Решает, какие [Tier|тиры] модов на нём могут появиться. Для крафта "
              "бери базы с высоким уровнем предмета (75+), иначе лучшие тиры недоступны. Не путать с требуемым "
              "уровнем персонажа.",
        "en": "The level the item dropped at. It decides which mod [Tier|tiers] can appear. For crafting pick bases "
              "of high item level (75+), or the best tiers are out of reach. Not the character level it requires."}),
    ("Corrupted", "basics", {"ru": "Порча (осквернение)", "en": "Corruption"}, {
        "ru": "Сфера ваал непредсказуемо меняет предмет и делает его «осквернённым». Такой предмет почти нельзя "
              "крафтить дальше, но носить — без штрафов. Портить стоит только то, что уже не будешь улучшать.",
        "en": "A Vaal Orb changes an item unpredictably and corrupts it. A corrupted item can hardly be crafted any "
              "more, but wearing it costs nothing. Corrupt only what you will not improve."}),
]

# the game's keyword ids some entries stand for too (the popups of those open ours)
ALIASES = {"Frozen": "Freeze", "LightStun": "Stun", "Abyssal": "Abyssalify", "Suffix": "Prefix"}


def entries(lang: str = "ru") -> dict[str, dict]:
    """id -> {"name", "nameLocal", "text", "textLocal", "group", "source": "poe2lab"} in the shape of the game's
    keywords, so the popups show them the same way."""
    out = {}
    for kid, group, names, text in ENTRIES:
        out[kid] = {"name": names["en"], "nameLocal": names.get(lang, names["en"]), "text": text["en"],
                    "textLocal": text.get(lang, text["en"]), "group": group, "source": "poe2lab"}
    for alias, kid in ALIASES.items():
        out.setdefault(alias, out[kid])
    return out


def groups(lang: str = "ru") -> list[dict]:
    """The page: groups in order, each with its entries in order."""
    by_group = {}
    for kid, group, _names, _text in ENTRIES:
        by_group.setdefault(group, []).append(kid)
    return [{"key": g, "name": names.get(lang, names["en"]), "ids": by_group.get(g, [])} for g, names in GROUPS]
