"""Farming strategies for the endgame section, in our own words: what a strategy farms, why it pays, where on the
atlas it runs, what to set up (waystone, tablets, atlas nodes, master) and how a map goes. Taken from players'
guide videos (data/transcripts, folders 26-45 and earlier) and checked against the game files where the game says
it: node texts (atlas.json), tablet modifiers (endgame.json), item names. Incomes are what the authors reported for
their own sessions in one league - a pointer, not a promise.

Links in "setup" open the program's own tools: {"maps": preset} the waystone stash search, {"tablets": preset} the
tablet stash search, {"atlas": [node names]} the nodes on the atlas tree, {"master": id} the atlas masters."""

# budget / build: 1 cheap or weak build is fine, 2 middling, 3 expensive or a strong build is a must
STRATEGIES = [
    {"id": "ritual", "icon": "skull", "option": "ritual", "budget": 1, "build": 1, "sources": [29, 28],
     "name": {"ru": "Ритуал: дань и откладывание", "en": "Ritual: tribute and deferring"},
     "goal": {"ru": "Омены и уникальные вещи за дань; головы Хозяина — проход в Безымянные.",
              "en": "Omens and uniques bought with tribute; the King's heads open the Nameless rites."},
     "why": {"ru": "Алтарь — магазин: валюта в нём дань, а дань дают монстры, убитые в круге. Больше монстров в "
                   "круге — больше дани — больше обновлений набора и откладываний — больше шансов увидеть дорогой "
                   "омен. Редкость предметов на набор алтаря не влияет.",
             "en": "An altar is a shop paid in tribute, and tribute comes from monsters killed in its circle. More "
                   "monsters, more tribute, more rerolls and defers, more chances at an expensive omen. Item rarity "
                   "does not touch the altar's offers."},
     "where": {"ru": "Любые карты 80+ уровня (16 тир или 15 тир +1): с 80 уровня в наборе появляются самые дорогие "
                     "омены. Открытые биомы — в коридорах круг маленький, монстров мало.",
               "en": "Any map of level 80+ (tier 16, or tier 15 +1): the dearest omens only appear from area level "
                     "80. Open biomes — a corridor makes a small circle with few monsters."},
     "setup": [
         {"what": "waystone", "text": {"ru": "Шапка камня: размер групп и редкость монстров. На камень с 6 свойствами — "
                                             "омены хаотичной редкости и хаотичной эффективности + сфера хаоса: они "
                                             "исключают редкость предметов и эффективность, остаются нужные строки.",
                                       "en": "The waystone's header: pack size and monster rarity. On a 6-modifier "
                                             "waystone: Omens of Chaotic Rarity and Chaotic Effectiveness + a Chaos Orb: "
                                             "they rule out item rarity and effectiveness, the lines you want stay."},
          "link": {"maps": "ritual"}},
         {"what": "tablets", "text": {"ru": "Две плитки Ритуала: больше дани + размер групп; третья — заражённая "
                                            "(поднимает уровень области) или ещё одна Ритуала.",
                                      "en": "Two Ritual tablets: more tribute + pack size; the third an Irradiated "
                                            "one (raises the area level) or another Ritual one."},
          "link": {"tablets": "ritual"}},
         {"what": "atlas", "text": {"ru": "Ветка Ритуала: «Терпеливое почитание» (откладывание на 50% дешевле), "
                                          "«Перерождение в тенях» (возрождённые чаще волшебные/редкие), "
                                          "«Заманчивые предложения», «Меж двух миров» + «Древняя вражда».",
                                    "en": "The Ritual branch: Patient Devotion (defers 50% cheaper), Reborn in "
                                          "Shadow (revived monsters more often magic/rare), Tempting Offers, Between "
                                          "Two Worlds + Ancient Enmities."},
          "link": {"atlas": ["Patient Devotion", "Reborn in Shadow", "Tempting Offers", "Between Two Worlds",
                             "Ancient Enmities"]}},
         {"what": "master", "text": {"ru": "Дориани: «Улучшенная калибровка» разгоняет шапку камня (размер групп).",
                                     "en": "Doryani: Improved Calibration makes the waystone's header bigger."},
          "link": {"master": "Doryani"}}],
     "steps": {"ru": ["По карте — от алтаря к алтарю (вороны показывают следующий), последний алтарь — в споте "
                      "босса: там просторно и монстров больше.",
                      "Дух азмири у алтаря (с узлами «Меж двух миров», «Древняя вражда») — гонять к монстрам, "
                      "иначе он забьётся в угол.",
                      "Обновлять набор, пока есть обновления; ценное — откладывать, выкупать в конце.",
                      "Перед выходом потратить всю дань: на покупку, откладывание или подношение Хозяину — она "
                      "сгорает."],
               "en": ["Go altar to altar (crows point to the next); do the last one in the boss's spot: it is open "
                      "and spawns more.",
                      "The Azmeri spirit at the altar (Between Two Worlds, Ancient Enmities): drag it to the "
                      "monsters, or it sits in a corner.",
                      "Reroll while you have rerolls; defer what is worth something, buy at the end.",
                      "Spend all the tribute before leaving — buy, defer or offer it to the King; it does not carry "
                      "over."]},
     "tips": {"ru": ["Откладывать одну вещь один раз за карту — хватает; со «Свободой веры» (+10% цены) повторное "
                     "откладывание уже дороже скидки.",
                     "Красная рамка — последнее появление: купить или отпустить."],
              "en": ["Defer an item once per map — enough; with Freedom of Faith (+10% prices) a second defer costs "
                     "more than it saves.",
                     "A red frame is the last showing: buy it or let it go."]},
     "profit": {"ru": "Стабильно; главный выигрыш — фиолетовые омены (15–20 div) и головы Хозяина.",
                "en": "Steady; the big wins are purple omens (15–20 div) and the King's heads."}},

    {"id": "nameless", "icon": "crown", "option": "ritual", "budget": 2, "build": 2, "sources": [29, 28],
     "name": {"ru": "Ритуал Безымянных", "en": "Nameless rites"},
     "goal": {"ru": "Цепочка из 5–6 карт, где обновлений набора с каждой картой больше.",
              "en": "A chain of 5–6 maps, each with more rerolls than the last."},
     "why": {"ru": "На каждой следующей карте цепочки обновлений на одно больше (2, 3 … 7), а уникальная плитка "
                   "«Свобода веры» удваивает их — до 14 обновлений: так находят самые дорогие омены. Боссы прошлых "
                   "карт возвращаются в ритуал.",
             "en": "Each map of the chain gives one more reroll (2, 3 … 7) and the unique Freedom of Faith tablet "
                   "doubles them — up to 14: that is how the dearest omens are found. Earlier maps' bosses come "
                   "back in the rite."},
     "where": {"ru": "Голова Хозяина (с босса Ритуала) → NPC в логове Ритуала (Кертарт) → выбрать 5 карт "
                     "(6 с узлом «Несмолкающие напевы»). Открытые биомы; награду — на городскую карту (больше дани).",
               "en": "A King's head (from the Ritual boss) → the NPC in the Ritual lair → pick 5 maps (6 with Ongoing "
                     "Chants). Open biomes; put the reward on a city map (more tribute)."},
     "setup": [
         {"what": "tablets", "text": {"ru": "«Свобода веры» (обновлять вдвое чаще, награды на 10–15% дороже) + "
                                            "плитки Ритуала: +обновления, больше дани, шанс предзнаменований.",
                                      "en": "Freedom of Faith (twice the rerolls, rewards 10–15% dearer) + Ritual "
                                            "tablets: more rerolls, more tribute, omen chance."},
          "link": {"tablets": "ritual"}},
         {"what": "waystone", "text": {"ru": "Камни 16 тира, размер групп от 20%.", "en": "Tier 16, pack size 20%+."},
          "link": {"maps": "ritual"}},
         {"what": "atlas", "text": {"ru": "«Несмолкающие напевы» (+1 карта), «Тёмное собрание», «Час Безымянных».",
                                    "en": "Ongoing Chants (+1 map), Umbral Gathering, Hour of the Nameless."},
          "link": {"atlas": ["Ongoing Chants", "Umbral Gathering", "Hour of the Nameless"]}}],
     "steps": {"ru": ["Пройти цепочку: на каждой карте все алтари, последний — у босса.",
                      "Откладывать один раз (новое или с красной рамкой) и обновлять до конца; выкупать в конце.",
                      "За каждую карту — «Зов теней»; 5 штук — босс Ритуала 3 тира.",
                      "Пока не убит босс Ритуала 2 тира, конец дерева Ритуала закрыт — убить его один раз."],
               "en": ["Run the chain: every altar on every map, the last at the boss.",
                      "Defer once (new items or red-framed ones) and reroll to the end; buy at the end.",
                      "Each map gives a Call of the Shadow; 5 of them open the tier 3 Ritual boss.",
                      "Until the tier 2 Ritual boss is killed the end of the Ritual tree stays locked — kill it "
                      "once."]},
     "tips": {"ru": ["Вариант «абуз» (Кардес): прикрепить голову к точке, соединённой с 5 картами, пройти маршрут "
                     "до предпоследней карты и посмотреть пул наград; нет фиолетового омена — сжечь голову (~1 div) "
                     "и брать следующую. Рискованно, окупается на дистанции; цены голов после ролика росли.",
                     "Чтобы награда легла на доступную карту — башни с уникальной плиткой «Великий план» (открывает "
                     "все карты вокруг)."],
              "en": ["The 'abuse' variant (Kardes): attach a head to a spot linked to 5 maps, walk the route to the "
                     "second-last map and look at its reward pool; no purple omen — burn the head (~1 div) and take "
                     "the next. Risky, pays over many tries; head prices rose after the video.",
                     "To land the reward on a reachable map: towers with the unique Grand Plan tablet (opens all "
                     "nearby maps)."]},
     "profit": {"ru": "По словам автора «абуза» — сотни div за 80 голов (~2 часа), с Mageblood (~215 div).",
                "en": "The 'abuse' author: hundreds of div from 80 heads (~2 hours), with a Mageblood (~215 div)."}},

    {"id": "fractures", "icon": "gem", "option": "currency", "budget": 2, "build": 2, "sources": [26, 38, 42],
     "name": {"ru": "Очищенные карты: раскалывающие сферы", "en": "Cleansed maps: Fracturing Orbs"},
     "goal": {"ru": "Раскалывающие сферы с очищенных монстров + дивайны, омены Бездны, Симулякры.",
              "en": "Fracturing Orbs from cleansed monsters + divines, Abyss omens, Simulacra."},
     "why": {"ru": "Раскалывающие сферы падают только с очищенных монстров, и только с узлом «Скрытые шрамы». "
                   "Редкие монстры дают больше всего добычи — их количество разгоняют плитки, мастер и камень.",
             "en": "Fracturing Orbs drop only from cleansed monsters, and only with the Hidden Scars node. Rare "
                   "monsters drop the most — tablets, the master and the waystone multiply them."},
     "where": {"ru": "Зоны порчи на атласе (красный кругляш со столбом света): убить босса порчи — зона станет "
                     "очищенной. Карты с «Замурованной яростью» (поиск на атласе) — гарантированная раскалывающая "
                     "сфера.",
               "en": "Corruption zones on the atlas (a red dot with a pillar of light): kill its boss and the zone "
                     "becomes cleansed. Maps with Entombed Fury (search the atlas) give a guaranteed Fracturing Orb."},
     "setup": [
         {"what": "waystone", "text": {"ru": "~100% редкости монстров в шапке: омены хаотичной редкости, количества "
                                             "и эффективности + хаос — исключают всё, кроме редкости монстров.",
                                       "en": "~100% Monster Rarity in the header: Chaotic Rarity, Quantity and "
                                             "Effectiveness omens + Chaos rule out everything but monster rarity."},
          "link": {"maps": "monsters"}},
         {"what": "tablets", "text": {"ru": "Три плитки РАЗНЫХ типов (Делириум, Бездна, Ритуал): на каждой «+1–2 "
                                            "случайных свойства карте» и редкость монстров. Бездна — треть дохода.",
                                      "en": "Three tablets of DIFFERENT types (Delirium, Abyss, Ritual): each with "
                                            "'+1–2 random map modifiers' and monster rarity. Abyss made a third of "
                                            "the income."},
          "link": {"tablets": "fractures"}},
         {"what": "atlas", "text": {"ru": "«Скрытые шрамы» (без него раскалывающих сфер нет), узлы на редких "
                                          "монстров и их свойства.",
                                    "en": "Hidden Scars (no Fracturing Orbs without it), nodes for rare monsters "
                                          "and their modifiers."},
          "link": {"atlas": ["Hidden Scars"]}},
         {"what": "master", "text": {"ru": "Хильда: «Сезон размножения» (+15% редких) и «Древние письмена» "
                                           "(+8% к плиткам за каждый разный тип).",
                                     "en": "Hilda: Breeding Season (+15% rares) and Ancient Inscriptions (+8% to "
                                           "tablets per different type)."},
          "link": {"master": "Hilda"}}],
     "steps": {"ru": ["Очищенные карты дополнительно «мазать» духами азмири или туманом Делириума 200%.",
                      "Делать каждый ритуал: убитый в круге очищенный монстр отдаёт раскалывающую сферу в конце.",
                      "Бездну — до Глубин, приглашения Кульмака не пропускать.",
                      "«Замурованная ярость»: Делириум + Ритуал + плитка повторного прохода — убить босса дважды."],
               "en": ["Coat cleansed maps with Azmeri spirits or 200% Delirium fog.",
                      "Do every Ritual: a cleansed monster killed in the circle gives its Fracturing Orb at the end.",
                      "Take the Abyss down to the Depths; don't skip Kulmak's invitations.",
                      "Entombed Fury: Delirium + Ritual + a replay tablet — kill the boss twice."]},
     "tips": {"ru": ["Плитки с третьим модом «эффективность» стоят втрое дороже — по словам автора, не окупаются."],
              "en": ["Tablets with a third 'effectiveness' modifier cost three times more — the author says they "
                     "don't pay off."]},
     "profit": {"ru": "Автор: 50 карт за ~5 часов — ~610 div при расходах ~150 div (≈90 div/час).",
                "en": "The author: 50 maps in ~5 hours — ~610 div against ~150 div spent (≈90 div/hour)."}},

    {"id": "circles", "icon": "keystone", "option": "currency", "budget": 1, "build": 2, "sources": [42],
     "name": {"ru": "Круги призыва + Делириум", "en": "Summoning circles + Delirium"},
     "goal": {"ru": "Раскалывающие сферы, густые эмоции, Симулякр, образцовые базы 82 — на дешёвых плитках.",
              "en": "Fracturing Orbs, potent emotions, Simulacra, exceptional item level 82 bases — on cheap tablets."},
     "why": {"ru": "Боссы кругов призыва в очищенных областях с узлом «Из неведомых далей» получают свойство, а с "
                   "таких — 5% шанс раскалывающей сферы. Плитки множат круги (4–6 боссов за карту), Делириум даёт "
                   "эмоции.",
             "en": "Circle bosses in cleansed areas get a modifier with From Distances Untold, and those have a 5% "
                   "Fracturing Orb chance. Tablets multiply the circles (4–6 bosses a map), Delirium adds emotions."},
     "where": {"ru": "Очищенные карты; карты с «+1 к уровню монстров» — Т16 + заражённая плитка = зона 82.",
               "en": "Cleansed maps; maps with '+1 monster level' — tier 16 + an Irradiated tablet = area 82."},
     "setup": [
         {"what": "tablets", "text": {"ru": "Смотрителя (круг призыва + эффективность), Делириума (круг + "
                                            "эффективность), на +1 картах — заражённая (круг + эффективность). "
                                            "Плитки по 5–15 ex.",
                                      "en": "Overseer (summoning circle + effectiveness), Delirium (circle + "
                                            "effectiveness), on +1 maps an Irradiated one (circle + effectiveness). "
                                            "5–15 ex each."},
          "link": {"tablets": "circles"}},
         {"what": "atlas", "text": {"ru": "«Владения Повелителя» (выбрать круги), «Повелитель рун», «Избранный "
                                          "путь» (круги), «Из неведомых далей», «Скрытые шрамы».",
                                    "en": "Overlord's Domain (pick circles), Lord of the Runes, The Chosen Path "
                                          "(circles), From Distances Untold, Hidden Scars."},
          "link": {"atlas": ["Overlord's Domain", "Lord of the Runes", "The Chosen Path", "From Distances Untold",
                             "Hidden Scars"]}},
         {"what": "master", "text": {"ru": "Джадо: «Частичный перевод» (до +40% к свойствам плиток) и "
                                           "«Внимательная оценка» (исключительные базы).",
                                     "en": "Jado: Partial Translation (up to +40% to tablet modifiers) and Keen "
                                           "Appraisal (exceptional bases)."},
          "link": {"master": "Jado"}}],
     "steps": {"ru": ["Сразу включить Делириум, искать круг и руны.",
                      "Руны активировать по одной и сразу вызывать босса: собранные заранее багуются (вызов только "
                      "дважды).",
                      "В конце завершить Делириум — осколки Симулякра."],
               "en": ["Start the Delirium at once, look for the circle and its runes.",
                      "Activate runes one at a time and summon right away: runes gathered first bug out (only two "
                      "summons).",
                      "End the Delirium at the end — Simulacrum splinters."]},
     "tips": {"ru": ["Густые эмоции подешевели после патча — основной доход теперь раскалывающие сферы и базы."],
              "en": ["Potent emotions got cheaper after a patch — the income is now Fracturing Orbs and bases."]},
     "profit": {"ru": "Автор: «за карту постоянно что-то свистит» при почти нулевых вложениях.",
                "en": "The author: something good drops every map, for next to no investment."}},

    {"id": "delirium", "icon": "eye", "option": "delirium", "budget": 3, "build": 3, "sources": [38],
     "name": {"ru": "Делириум 200% на очищенных картах", "en": "200% Delirium on cleansed maps"},
     "goal": {"ru": "Раскалывающие сферы, эмоции (для крафта самоцветов), осколки Симулякра.",
              "en": "Fracturing Orbs, emotions (for jewel crafting), Simulacrum splinters."},
     "why": {"ru": "Безумие тумана (до 100%, с Большого зеркала до 200%) усиливает монстров и их добычу и "
                   "добавляет монстров. Свойство плитки «туман накладывает больше бредовости» с «Частичным "
                   "переводом» растёт сильнее, чем сумма плиток.",
             "en": "The fog's delirium (up to 100%, 200% from a Grand Mirror) makes monsters and their loot "
                   "stronger and adds monsters. The tablet modifier 'more delirium from the fog' grows faster than "
                   "the sum of the tablets with Partial Translation."},
     "where": {"ru": "Зоны порчи → очищенные карты, покрытые туманом от Большого зеркала.",
               "en": "Corruption zones → cleansed maps covered by a Grand Mirror's fog."},
     "setup": [
         {"what": "waystone", "text": {"ru": "6 свойств для обычных карт, 8 (осквернённые) — для очищенных; "
                                             "эффективность и редкость монстров.",
                                       "en": "6 modifiers for normal maps, 8 (corrupted) for cleansed ones; "
                                             "effectiveness and monster rarity."},
          "link": {"maps": "juiced"}},
         {"what": "tablets", "text": {"ru": "Три плитки Делириума: «+15–30% бредовости» и эффективность монстров.",
                                      "en": "Three Delirium tablets: '+15–30% delirium' and monster effectiveness."},
          "link": {"tablets": "delirium_fog"}},
         {"what": "atlas", "text": {"ru": "Всё дерево Делириума; «Повторяющиеся кошмары» переключать на "
                                          "распространение тумана только когда наносите туман.",
                                    "en": "The whole Delirium tree; switch Recurring Nightmares to spreading the "
                                          "fog only while you place it."},
          "link": {"atlas": ["Recurring Nightmares"]}},
         {"what": "master", "text": {"ru": "Джадо: «Частичный перевод», «Неожиданные задания».",
                                     "en": "Jado: Partial Translation, Unexpected Missions."},
          "link": {"master": "Jado"}}],
     "steps": {"ru": ["Идти к зонам порчи на осквернённых шестимодовых камнях с тремя плитками Делириума.",
                      "На карте: хрупкие зеркала (монстры, осколки), цветные (оранжевое — босс, красное — трясины).",
                      "После Большого зеркала — чёрное зеркало в убежище: покрыть туманом очищенные карты.",
                      "Перед очищенными картами довести туман до 200%; в конце — «завершить Делириум»."],
               "en": ["Head for corruption zones on corrupted 6-mod waystones with three Delirium tablets.",
                      "On a map: fragile mirrors (monsters, splinters), coloured ones (orange — a boss, red — the "
                      "Mires).",
                      "After a Grand Mirror — the black mirror in the hideout: cover cleansed maps with fog.",
                      "Bring the fog to 200% before cleansed maps; End the Delirium at the end."]},
     "tips": {"ru": ["Нужен очень сильный билд: монстры с кучей свойств, 230% бреда.",
                     "Баг (сентябрь): после трясин нельзя двигаться — завершить карту до входа в портал."],
              "en": ["You need a very strong build: monsters with many modifiers, 230% delirium.",
                     "A bug (September): after the Mires you can't move — finish the map before the portal."]},
     "profit": {"ru": "Автор: 75+ div/час.", "en": "The author: 75+ div/hour."}},

    {"id": "expedition", "icon": "hammer", "option": "expedition", "budget": 1, "build": 2, "sources": [27, 36],
     "name": {"ru": "Экспедиция: от бюджетной до обмазанной", "en": "Expedition: budget to juiced"},
     "goal": {"ru": "Валюта с сундуков, реликты дороже 1 div, саги с лаки-дропами.",
              "en": "Currency from chests, remnants worth over 1 div, sagas with lucky drops."},
     "why": {"ru": "Монстры экспедиции «подкручены» по добыче, а большие экспедиции почти без вложений дают 2–4 "
                   "div стабильно. Обмазанная (эффективность ~86%) — больше, но для очень сильного билда.",
             "en": "Expedition monsters drop a lot, and big expeditions give 2–4 div steadily for almost nothing. "
                   "Juiced (~86% effectiveness) gives more, for a very strong build."},
     "where": {"ru": "Журналы экспедиции (~0.25 div или с карт): кораблик в инвентаре открывает острова — "
                     "большие экспедиции, боссы саг, обычные карты.",
               "en": "Expedition logbooks (~0.25 div or from maps): the ship icon opens the islands — big "
                     "expeditions, saga bosses, normal maps."},
     "setup": [
         {"what": "other", "text": {"ru": "Открыть: квест «Искатель рун» (4 акт, 4 обрывка карты) → Фарул в "
                                          "убежище Зиккурата → развалины Кингсмарша → 4 босса + Олрот.",
                                    "en": "Unlock: the Runeseeker quest (act 4, 4 map pieces) → Farrul in the "
                                          "Ziggurat hideout → Kingsmarch ruins → 4 bosses + Olroth."}},
         {"what": "tablets", "text": {"ru": "Заражённые плитки (на больших экспедициях, по словам автора, другие не "
                                            "работают): эффективность, количество редких, редкость предметов.",
                                      "en": "Irradiated tablets (on big expeditions others don't work, the author "
                                            "says): effectiveness, rare monster count, item rarity."},
          "link": {"tablets": "expedition"}},
         {"what": "master", "text": {"ru": "Джадо: «Восточные знания» (второй ролл реликта), «Нерассказанные "
                                           "истории», «Частичный перевод», «Неожиданные задания».",
                                     "en": "Jado: Eastern Knowledge (a remnant's second roll), Untold Histories, "
                                           "Partial Translation, Unexpected Missions."},
          "link": {"master": "Jado"}},
         {"what": "waystone", "text": {"ru": "Бюджетно — «по толщинке» (оставить возрождения); уверенно — 6 свойств; "
                                             "обмазанно — омены хаотичной редкости, количества и монстров + хаос (исключают всё, кроме эффективности) → ~86%.",
                                       "en": "Budget: a thick one (keep revives); confident: 6 modifiers; juiced: "
                                             "Chaotic Rarity, Quantity and Monsters omens + Chaos (everything but "
                                             "effectiveness ruled out) → ~86%."},
          "link": {"maps": "juiced"}}],
     "steps": {"ru": ["Проверить все реликты (Ancient Price Helper показывает цены); дешевле 1 div — перероллить "
                      "жидким веризием или пропустить.",
                      "Взрывами цеплять сундуки с валютой (особенно золотые), плохие реликты не задевать.",
                      "Саги: Медведя (камень Вораны), Олрота (окупается трискелионом), Утреда (шанс руны маны "
                      "→ ~480 div).",
                      "Обмазанная: взорвать цепочку реликтов, последним — с 9 рунами."],
               "en": ["Check every remnant (Ancient Price Helper shows prices); under 1 div — reroll with Liquid "
                      "Verisium or skip.",
                      "Aim explosions at currency chests (gold ones especially), keep off bad remnants.",
                      "Sagas: Medved's (Vorana's gem), Olroth's (pays back with the triskelion), Uhtred's (a chance at "
                      "the mana rune → ~480 div).",
                      "Juiced: blow a chain of remnants, the 9-rune one last."]},
     "tips": {"ru": ["Контент примерно вдвое тяжелее шестимодовых Т15 — начинать, когда они идут спокойно.",
                     "Сага Альдура удалена."],
              "en": ["About twice as hard as 6-mod tier 15 maps — start when those are easy.",
                     "Aldur's Saga was removed."]},
     "profit": {"ru": "Автор: ~500 div за 2 дня; бюджетная большая экспедиция 2–4 div, обмазанная ~5 div.",
                "en": "The author: ~500 div in 2 days; a budget big expedition 2–4 div, a juiced one ~5 div."}},

    {"id": "strongboxes", "icon": "chest", "option": "currency", "budget": 3, "build": 2, "sources": [44, 37],
     "name": {"ru": "Духи азмири в ларцах (города)", "en": "Azmeri spirits in strongboxes (cities)"},
     "goal": {"ru": "Дивайны и сферы отмены с монстров ларцов, образцовые базы.",
              "en": "Divines and Orbs of Annulment from strongbox monsters, exceptional bases."},
     "why": {"ru": "Дух зайца вселяется в ларец; его монстры получают свойства духов, рун реликтов и ваал-реликтов "
                   "— чем больше свойств, тем больше добычи. Повторные открытия ларца множат монстров.",
             "en": "The hare spirit possesses a strongbox; its monsters get the spirits', remnant runes' and Vaal "
                   "relics' modifiers — more modifiers, more loot. Opening it again multiplies the monsters."},
     "where": {"ru": "Города изамитов или ваал (рунные монолиты дают ещё духов).",
               "en": "Ezomyte or Vaal cities (runic monoliths add spirits)."},
     "setup": [
         {"what": "tablets", "text": {"ru": "3 Смотрителя (ларцы, духи азмири, количество редких) + 1 Экспедиции "
                                            "(2 ваал-реликта, доп. рунное свойство, духи; без закопанных ларцов).",
                                      "en": "3 Overseer (strongboxes, Azmeri spirits, rare count) + 1 Expedition "
                                            "(2 Vaal relics, extra runic modifier, spirits; no buried strongboxes)."},
          "link": {"tablets": "strongboxes"}},
         {"what": "waystone", "text": {"ru": "Редкость монстров ≥100%: омены хаотичной редкости, количества и "
                                             "эффективности + хаос; осквернить → 8 свойств или Т16.",
                                       "en": "Monster Rarity ≥100%: Chaotic Rarity, Quantity and Effectiveness "
                                             "omens + Chaos; corrupt → 8 modifiers or tier 16."},
          "link": {"maps": "monsters"}},
         {"what": "atlas", "text": {"ru": "«Живой металл» (духи вселяются в ларцы), «Потайные отсеки», «Вражеские "
                                          "запасы».",
                                    "en": "Living Metal (spirits possess strongboxes), Hidden Compartments, Enemy's "
                                          "Hoard."},
          "link": {"atlas": ["Living Metal", "Hidden Compartments", "Enemy's Hoard"]}},
         {"what": "master", "text": {"ru": "Хильда (бюджетные плитки) или Джадо при 230%+ редких монстров.",
                                     "en": "Hilda (budget tablets) or Jado at 230%+ rare monsters."},
          "link": {"master": "Hilda"}}],
     "steps": {"ru": ["Зачистить карту, не будя зайца; провести духа к ларцу.",
                      "Ларец: редкость и эффективность монстров ларца, «две группы редких» (божественной сферой).",
                      "Открыть скрытым ключом; заяц не перелетел — Omen of the Hunt; повторно — Omen of Secret "
                      "Compartments.",
                      "Руна перерождения в коронке реликта ломает зайца — перероллить или не трогать."],
               "en": ["Clear the map without waking the hare; lead the spirit to a strongbox.",
                      "The strongbox: its monsters' rarity and effectiveness, 'two rare packs' (Divine Orb).",
                      "Open with a Hidden Key; if the hare didn't move — Omen of the Hunt; again — Omen of Secret "
                      "Compartments.",
                      "A rebirth rune in a remnant's crown breaks the hare — reroll it or leave it."]},
     "tips": {"ru": ["Скрытый ключ к закопанным ларцам запретили (патч 0.5.5d)."],
              "en": ["Hidden Keys on buried strongboxes were disallowed (patch 0.5.5d)."]},
     "profit": {"ru": "Автор: средняя карта ~47 div; образцовая база с 30% качества ~300 div.",
                "en": "The author: an average map ~47 div; an exceptional base at 30% quality ~300 div."}},

    {"id": "breach_t1", "icon": "spark", "option": "breach", "budget": 1, "build": 1, "sources": [40],
     "name": {"ru": "Разлом на Т1: обильные дары утробы", "en": "Breach on tier 1: Lavish Wombgifts"},
     "goal": {"ru": "Катализаторы из обильных даров утробы — для слабого билда.",
              "en": "Catalysts from Lavish Wombgifts — for a weak build."},
     "why": {"ru": "Добыча обильных даров не зависит от их уровня, а кровь — зависит: дар 65 уровня ест 100 крови, "
                   "82-го — 1000. Значит дары фармят на Т1, а кровь — отдельно.",
             "en": "A Lavish Wombgift's loot does not depend on its level, but its blood cost does: level 65 eats "
                   "100 blood, level 82 — 1000. So farm gifts on tier 1 and blood separately."},
     "where": {"ru": "Дары — Т1 вне городов (по пути); кровь — Т16 в городе.",
               "en": "Gifts — tier 1 outside cities (on the way); blood — tier 16 in a city."},
     "setup": [
         {"what": "tablets", "text": {"ru": "Набор 1: «+30–60% даров утробы». Набор 2: «+30–60% крови улья» "
                                            "(~3000 крови с карты на 4 плитки).",
                                      "en": "Set 1: '+30–60% Wombgifts'. Set 2: '+30–60% Hiveblood' (~3000 blood a "
                                            "map with 4 tablets)."},
          "link": {"tablets": "wombgifts"}},
         {"what": "atlas", "text": {"ru": "Ветка Разлома: узел на обильные дары; узлы на уровень дара не брать.",
                                    "en": "The Breach branch: the Lavish gift node; skip the gift-level ones."},
          "link": {"part": "Breach"}}],
     "steps": {"ru": ["Набрать ~100 000 крови в одном городе.", "Открывать дары 65 уровня до бесконечности."],
               "en": ["Farm ~100 000 blood in one city.", "Open level 65 gifts endlessly."]},
     "tips": {"ru": ["Можно продавать сами дары (6–8 хаосов) — по словам автора, примерно тот же доход."],
              "en": ["You can sell the gifts themselves (6–8 chaos) — about the same income, the author says."]},
     "profit": {"ru": "Автор: 500 даров (~80 карт) → ~320 div.", "en": "The author: 500 gifts (~80 maps) → ~320 div."}},

    {"id": "abyss", "icon": "drop", "option": "abyss", "budget": 1, "build": 2, "sources": [51, 26],
     "name": {"ru": "Бездна: предзнаменования света", "en": "Abyss: Omens of Light"},
     "goal": {"ru": "Омены света и эха с редких Аманаму (~9–10 div), раскалывающие сферы с очищенных зон.",
              "en": "Omens of Light and Echoes from rare Amanamu (~9–10 div), Fracturing Orbs from cleansed zones."},
     "why": {"ru": "Редкие монстры Аманаму из провалов Бездны роняют омены света — если убить их вне их тучи. Ключевой "
                   "узел Бездны гарантирует Аманаму на карте, плитки добавляют монстрам свойства Бездны.",
             "en": "Rare Amanamu monsters from the Abyss chasms drop Omens of Light — if killed outside their cloud. "
                   "The Abyss keystone guarantees Amanamu on the map, tablets give monsters more Abyss modifiers."},
     "where": {"ru": "Любые карты с Бездной; лучше — очищенные зоны (ещё и раскалывающие сферы). Карта ~3–4 минуты.",
               "en": "Any map with an Abyss; cleansed zones are better (Fracturing Orbs too). ~3–4 minutes a map."},
     "setup": [
         {"what": "atlas", "text": {"ru": "Ветка Бездны целиком (квесты — все 35 очков): «Повелитель Ямы» — выбрать "
                                          "Аманаму, омены, +20% к доп. провалу. Основное древо: везде эффективность, "
                                          "обязательно «Скрытые шрамы».",
                                    "en": "The whole Abyss branch (its quests give all 35 points): Lord of the Pit — "
                                          "pick Amanamu, omens, +20% extra chasm. The main tree: effectiveness "
                                          "wherever there is a choice, and Hidden Scars."},
          "link": {"atlas": ["Lord of the Pit", "Hidden Scars"]}},
         {"what": "waystone", "text": {"ru": "Т15 → алхимия → экзальты до 0 возрождений → омены хаотичной эффективности и "
                                             "количества + хаос: остаются редкость предметов и монстров (~100% вместе).",
                                       "en": "Tier 15 → Alchemy → Exalts to 0 revives → Chaotic Effectiveness and "
                                             "Quantity omens + Chaos: item and monster rarity stay (~100% together)."},
          "link": {"maps": "monsters"}},
         {"what": "tablets", "text": {"ru": "Три плитки (в городе — четыре): редкость на карте + «монстры Бездны чаще "
                                            "со свойствами Бездны». Третий мод «очерняющая валюта» не окупается.",
                                      "en": "Three tablets (four in a city): map rarity + 'Abyss monsters more often "
                                            "with Abyss modifiers'. A third 'desecrated currency' modifier doesn't pay."},
          "link": {"tablets": "abyss"}},
         {"what": "master", "text": {"ru": "Дориани: эффективность и редкость за свойства карты, «Улучшенная "
                                           "калибровка», «Скрытые закономерности» (открыть ближние карты).",
                                     "en": "Doryani: effectiveness and rarity per map modifier, Improved Calibration, "
                                           "Hidden Patterns (open nearby maps)."},
          "link": {"master": "Doryani"}}],
     "steps": {"ru": ["Зачищать провалы; редкого Аманаму (над ним свойство, он выпускает тучу) убивать ВНЕ тучи — "
                      "быстро или выведя из неё.",
                      "Выпал Omen of Light — всё правильно; «очищение» вместо него — убили в туче.",
                      "Глубины Бездны по времени не окупаются; «Lightless Void» — 1–2 проходки к Кулимаку (~2 div)."],
               "en": ["Clear the chasms; kill the rare Amanamu (its modifier shows, it releases a cloud) OUTSIDE the "
                      "cloud — fast, or after pulling it out.",
                      "An Omen of Light drops — done right; a purification omen instead — it died in the cloud.",
                      "The Abyss Depths don't pay for their time; a Lightless Void gives 1–2 Kulmak keys (~2 div)."]},
     "tips": {"ru": ["Двигаться к очищенным зонам, остальные карты — по пути, быстро."],
              "en": ["Head for the cleansed zones; the maps on the way — quickly."]},
     "profit": {"ru": "Автор: 50 карт — 220 div флэтом (омены света 107) при расходах ~25 div, ≈50 div/час.",
                "en": "The author: 50 maps — 220 div flat (Omens of Light 107) for ~25 div spent, ≈50 div/hour."}},

    {"id": "atlas_route", "icon": "map", "option": "bosses", "budget": 1, "build": 2, "sources": [60, 22],
     "name": {"ru": "Атлас для работяги: цитадели и аномалии", "en": "The atlas for a worker: citadels and anomalies"},
     "goal": {"ru": "Проходки на Арбитров, головы Хозяина и шанс династических камней (Гарухан ~350 div).",
              "en": "Arbiter fragments, King's heads and a chance at Lineage gems (Garukhan ~350 div)."},
     "why": {"ru": "Без дорогого «обмаза»: идёшь по атласу и берёшь ключевые точки. Количество путевых камней на плитках "
                   "увеличивает число проходок с босса цитадели; династические камни аномалий от модов карты не "
                   "зависят — их бегают на синих картах.",
             "en": "No expensive juicing: walk the atlas and take its key points. Waystone quantity on tablets raises "
                   "a citadel boss's fragment count; anomaly Lineage gems don't depend on map modifiers — run them on "
                   "magic maps."},
     "where": {"ru": "Цитадели (луч света; всегда на городах), аномальные карты: Нефритовые острова (Ракиата), "
                     "Священный водоём (Гарухан), замок с огоньками (Ригвальд); залы матриарха и патриарха.",
               "en": "Citadels (a beam of light; always on cities), anomaly maps: Jade Isles (Rakiata), Sacred "
                     "Reservoir (Garukhan), the bat castle (Rigwald); the Matriarch's and Patriarch's halls."},
     "setup": [
         {"what": "tablets", "text": {"ru": "На цитадель — 4 плитки любой базы с «увеличением количества находимых путевых "
                                            "камней» (~37%+, по 5–15 ex); 4-я ячейка — «Промышленные улучшения».",
                                      "en": "For a citadel — 4 tablets of any base with 'increased quantity of waystones "
                                            "found' (~37%+, 5–15 ex each); the 4th slot comes from Industrial "
                                            "Improvements."},
          "link": {"tablets": "waystones"}},
         {"what": "atlas", "text": {"ru": "«Воспоминания ваал / маракетов / каруи / эзомитов» (+15% второго "
                                          "династического камня), «Промышленные улучшения».",
                                    "en": "Memories of the Vaal / Maraketh / Karui / Ezomytes (+15% a second Lineage "
                                          "gem), Industrial Improvements."},
          "link": {"atlas": ["Memories of the Vaal", "Memories of the Maraketh", "Memories of the Karui",
                             "Memories of the Ezomytes", "Industrial Improvements"]}},
         {"what": "master", "text": {"ru": "Джадо до 4 уровня (по одной аномалии каждого вида): «Неожиданные задания», "
                                           "«Непредвиденные угрозы», «Частичный перевод», «Нерассказанные истории».",
                                     "en": "Jado to level 4 (one anomaly of each kind): Unexpected Missions, "
                                           "Unforeseen Threats, Partial Translation, Untold Histories."},
          "link": {"master": "Jado"}},
         {"what": "waystone", "text": {"ru": "По пути — шестимодовые осквернённые Т15 (Т16 после осквернения продавать); "
                                             "слабому билду — 4 мода (2 возрождения).",
                                       "en": "On the way — corrupted 6-modifier tier 15 (sell the tier 16 that corrupting "
                                             "makes); a weak build — 4 modifiers (2 revives)."}}],
     "steps": {"ru": ["Проходить башни — открывают обзор, видно лучи цитаделей.",
                      "Нефритовые острова: маяк на одной из соседних карт; водоём: пройти все карты с ветерками; "
                      "замок: идти за огоньками.",
                      "Встреча с Хозяином в инвентаре — на атласе видна «суть небытия»: по пути — убить босса Ритуала "
                      "(голова Хозяина)."],
               "en": ["Run the towers — they reveal the area and the citadels' beams.",
                      "Jade Isles: a beacon on one of the maps around; the reservoir: run every map with wind "
                      "trails; the castle: follow the wisps.",
                      "An Audience with the King in your bag shows the 'essence of oblivion' on the atlas: on the way, "
                      "kill the Ritual boss (a King's head)."]},
     "tips": {"ru": ["В медную цитадель плитки не вставляются (баг) — поэтому её проходки дороже."],
              "en": ["The copper citadel takes no tablets (a bug) — that's why its fragments cost more."]},
     "profit": {"ru": "Автор: ~78 div за вечер без единого династического камня, плюс Т16, плитки, базы.",
                "en": "The author: ~78 div an evening without a single Lineage gem, plus tier 16s, tablets, bases."}},

    {"id": "craft_tablets", "icon": "layers", "option": None, "budget": 1, "build": 1, "sources": [37, 46, 52],
     "name": {"ru": "Заработок: крафт плиток", "en": "Money: crafting tablets"},
     "goal": {"ru": "Плитки за 2–200 div из основ по 2–35 хаосов: Смотрителя, заражённые, Бездны.",
              "en": "Tablets worth 2–200 div from 2–35 chaos bases: Overseer, Irradiated, Abyss."},
     "why": {"ru": "Плитки — «лопаты» для чужого фарма: их покупают всегда, а у модов плиток один тир, поэтому хватает "
                   "самых дешёвых сфер. Ценные моды: заражённые — «+1–2 случайных свойства карте» (с эффективностью "
                   "15–50 div), Смотрителя — ларцы, духи, редкие, Бездны — «в 2 раза выше шанс наград в провалах», "
                   "«4 доп. провала».",
             "en": "Tablets are the shovels of other people's farming: they always sell, and a tablet's modifiers have "
                   "one tier, so the cheapest orbs do. Valuable modifiers: Irradiated — '+1–2 random map modifiers' "
                   "(15–50 div with effectiveness), Overseer — strongboxes, spirits, rares, Abyss — 'twice the chasm "
                   "rewards chance', '4 extra chasms'."},
     "where": {"ru": "Убежище: стопка плиток Смотрителя на 10 зарядов + сферы хаоса.",
               "en": "The hideout: a stack of 10-charge Overseer tablets + Chaos Orbs."},
     "setup": [
         {"what": "tablets", "text": {"ru": "Поиск плиток в складе с нужными модами подсвечивает удачные после "
                                            "каждого хаоса.",
                                      "en": "The tablet stash search highlights the good ones after each Chaos."},
          "link": {"tablets": "strongboxes"}}],
     "steps": {"ru": ["Купить плитки с 10 зарядами (фильтр зарядов на трейде; неопознанные синие — по 2–4 хаоса).",
                      "Опознать всё (Ctrl-клик по Дариане), усилить до 2 модов; поиском склада найти ценные.",
                      "С ценным модом — сфера царей + экзальт до 4; без — алхимия и снова поиск; Смотрителя — хаосом.",
                      "Префикс с числом 1 (ларцы, духи, +свойства карте) — божественной сферой до 2.",
                      "Цену смотреть оценкой оверлея; остаток — по 9 хаосов и снижать до 4–5."],
               "en": ["Buy 10-charge tablets (charge filter on the trade site; unidentified magic ones for 2–4 chaos).",
                      "Identify all (Ctrl-click Doryani), augment to 2 modifiers; find the valuable ones with the "
                      "stash search.",
                      "With a valuable modifier — Regal + Exalt to 4; without — Alchemy and search again; Overseer "
                      "ones — Chaos.",
                      "A prefix at 1 (strongboxes, spirits, +map modifiers) — a Divine Orb raises it to 2.",
                      "Price them with the overlay's estimate; the rest at 9 chaos, lowered to 4–5."]},
     "tips": {"ru": ["Редкие (4 мода) плитки — только после убийства Арбитра и узла «Обратная транскрипция»."],
              "en": ["Rare (4-modifier) tablets only after killing the Arbiter and the Reverse Transcription node."]},
     "profit": {"ru": "Автор: из ~20 div — плиток на 50–55 div.", "en": "The author: ~20 div in, 50–55 div of tablets out."}},

    {"id": "craft_desecrate", "icon": "helm", "option": None, "budget": 2, "build": 1, "sources": [57, 49, 31, 34],
     "name": {"ru": "Заработок: броня через очернение (тапки, тиары)", "en": "Money: armour through desecration (boots, tiaras)"},
     "goal": {"ru": "Сандалии Сихемы и тиары 82 уровня на 300+ ES: 1–60 div за вещь, партия ~4–5 div.",
              "en": "Item level 82 Sandals of Sihema and tiaras with 300+ ES: 1–60 div each, ~4–5 div a batch."},
     "why": {"ru": "Предзнаменование разложения + кость делают из вещи шесть очернений; в Колодце душ из каждых трёх "
                   "вариантов выбираешь лучший — по сути, сам собираешь вещь. Тиары носит половина игроков.",
             "en": "An Omen of Putrefaction + a bone turn an item into six desecrated modifiers; at the Well of Souls you "
                   "pick the best of each three — you build the item yourself. Half the players wear a tiara."},
     "where": {"ru": "Убежище и Колодец душ (2 акт, Бесплодные земли мастодонтов).",
               "en": "The hideout and the Well of Souls (act 2, the Mastodon Badlands)."},
     "setup": [],
     "steps": {"ru": ["Жёлтая база 82 уровня без очернения: качество 20, все гнёзда, руны железа — после очернения "
                      "ничего не добавить.",
                      "Omen of Putrefaction + кость → 6 очернений; раскрывать в Колодце.",
                      "Сначала префиксы: плоский ES (бывает один — брать сразу), потом процентный; Omen of Abyssal Echoes "
                      "— только когда вещь уже удачная (тапки: 35% скорости + 300 ES).",
                      "Суффиксы: резисты (хаос >20 — топ), редкость, критшанс (тиары), +2 миньонов."],
               "en": ["An item level 82 rare base, not desecrated: quality 20, all sockets, iron runes — nothing can be "
                      "added after.",
                      "Omen of Putrefaction + a bone → 6 desecrated modifiers; reveal them at the Well.",
                      "Prefixes first: flat ES (there is only one — take it), then percent; an Omen of Abyssal Echoes "
                      "only once the item is already good (boots: 35% speed + 300 ES).",
                      "Suffixes: resistances (chaos >20 is top), rarity, crit chance (tiaras), +2 minions."]},
     "tips": {"ru": ["Тир числа в колодце не виден — сверять с poe2db / Craft of Exile.",
                     "300 энергощита на тапках — порог, после которого цена резко растёт; 20% скорости уже плохо продаются."],
              "en": ["The well doesn't show a number's tier — check poe2db / Craft of Exile.",
                     "300 energy shield on boots is the line after which the price jumps; 20% speed sells poorly."]},
     "profit": {"ru": "Кардес: за день из 80 div стало 160 + тапок на ~200 div.",
                "en": "Kardes: 80 div became 160 in a day + ~200 div of boots on sale."}},

    {"id": "craft_jewels", "icon": "jewel", "option": None, "budget": 1, "build": 1, "sources": [43, 45],
     "name": {"ru": "Заработок: дешёвый крафт самоцветов и колец", "en": "Money: cheap jewel and ring crafting"},
     "goal": {"ru": "Самоцветы на 2–77 div и синие кольца на 2–9 div из дешёвых баз.",
              "en": "Jewels worth 2–77 div and magic rings worth 2–9 div from cheap bases."},
     "why": {"ru": "У модов самоцветов нет тиров — годится самая дешёвая сфера усиления; кольца 75+ с "
                   "совершенным превращением сразу дают Т1 урон к атакам.",
             "en": "Jewel modifiers have no tiers — the cheapest Augmentation will do; level 75+ rings with a "
                   "Perfect Transmutation get tier 1 attack damage at once."},
     "where": {"ru": "Убежище и верстак перековки (3 акт: Расплавленные залы → молот Освальду).",
               "en": "The hideout and the reforging bench (act 3: the Molten Vault → the hammer to Oswald)."},
     "setup": [],
     "steps": {"ru": ["Самоцветы: синие с одним модом из топа poe.ninja → усиление → хорошие: регал + экзальты, "
                      "плохие: алхимия, мусор: перековка 3→1.",
                      "Кольца (золотые 75+): совершенные превращение + усиление; редкость + резист уже ~9 div "
                      "синим.",
                      "Эмоции Делириума дописывают гарантированный мод вместо случайного суффикса."],
               "en": ["Jewels: magic ones with one modifier from poe.ninja's top → Augmentation → good: Regal + "
                      "Exalts, bad: Alchemy, junk: reforge 3→1.",
                      "Rings (Gold, 75+): Perfect Transmutation + Augmentation; rarity + resistance is ~9 div "
                      "already as magic.",
                      "Delirium emotions write a guaranteed modifier over a random suffix."]},
     "tips": {"ru": [], "en": []},
     "profit": {"ru": "Автор самоцветов: ~10 div вложений → 100+ div.", "en": "The jewel author: ~10 div in → 100+ div."}},
]

# a strategy's picture: an item of the game that stands for it (English name; poe2lab.endgame.item_art)
ART = {'ritual': 'Ritual Tablet',
       'nameless': 'Head of the King',
       'fractures': 'Fracturing Orb',
       'circles': 'Overseer Tablet',
       'delirium': 'Simulacrum',
       'expedition': 'Expedition Logbook',
       'strongboxes': 'Omen of Secret Compartments',
       'breach_t1': 'Lavish Wombgift',
       'abyss': 'Omen of Light',
       'atlas_route': 'Waystone (Tier 15)',
       'craft_tablets': 'Irradiated Tablet',
       'craft_desecrate': 'Omen of Putrefaction',
       'craft_jewels': 'Sapphire'}

LEVELS = {1: {"ru": "дёшево", "en": "cheap"}, 2: {"ru": "средне", "en": "middling"}, 3: {"ru": "дорого", "en": "expensive"}}
BUILDS = {1: {"ru": "любой билд", "en": "any build"}, 2: {"ru": "крепкий билд", "en": "a sturdy build"},
          3: {"ru": "очень сильный билд", "en": "a very strong build"}}


def strategies(lang: str = "ru", art: dict[str, str] | None = None) -> list[dict]:
    """The strategies with their texts in `lang` (English where it has none) and their pictures (name -> file)."""
    art = art or {}
    pick = lambda t: t.get(lang, t["en"]) if isinstance(t, dict) else t  # noqa: E731
    out = []
    for s in STRATEGIES:
        out.append({"id": s["id"], "icon": s["icon"], "img": art.get(ART.get(s["id"], ""), ""),
                    "option": s["option"], "sources": s["sources"],
                    "budget": s["budget"], "build": s["build"],
                    "budgetText": pick(LEVELS[s["budget"]]), "buildText": pick(BUILDS[s["build"]]),
                    **{k: pick(s[k]) for k in ("name", "goal", "why", "where", "steps", "tips", "profit")},
                    "setup": [{"what": x["what"], "text": pick(x["text"]), "link": x.get("link")} for x in s["setup"]]})
    return out
