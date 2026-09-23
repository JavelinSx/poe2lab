"""The build's skills as a player reads them: each skill with its support gems - why a support applies, what it
does in the game's own words, what it is worth in PoB - the mechanics that tie skills together (one skill
creates or inflicts something, another uses it up), and when each gem becomes available while levelling.

Links between skills are not a database of combinations: a short dictionary of the game's mechanics (Impale,
Ice Crystals, Freeze, charges, Rage...) says how a gem's own description and stat ids show that it creates or
uses one; every pair in the build is then found by matching. Numbers come from PoB what-ifs."""
import re
from dataclasses import dataclass

from .. import keywords as kw
from .gradients import metric_changes

# Area level from which each uncut gem level drops (the game's BaseItemTypes.DropLevel, patch 0.5): a skill gem of
# tier T is cut from an uncut skill gem of level T, a support of tier T from an uncut support gem of level T.
UNCUT_SKILL_AREA = {1: 1, 2: 4, 3: 7, 4: 11, 5: 15, 6: 19, 7: 23, 8: 27, 9: 32, 10: 37, 11: 42, 12: 47, 13: 53,
                    14: 59, 15: 62, 16: 62, 17: 62, 18: 62, 19: 62, 20: 62}
UNCUT_SUPPORT_AREA = {1: 1, 2: 16, 3: 33, 4: 45, 5: 55}
SUPPORT_STAGES = sorted(set(UNCUT_SUPPORT_AREA.values()))
OPTIONS = 4  # alternatives shown per levelling stage

# skill types a support requires, in the words of the Russian client
TYPE_RU = {
    "Attack": "атака", "Spell": "чары", "Melee": "ближний бой", "MeleeSingleTarget": "удар по одной цели",
    "Projectile": "снаряд", "Area": "область", "Duration": "длительность", "Damage": "урон", "Slam": "удар по земле",
    "Strike": "удар", "Warcry": "боевой клич", "Mark": "метка", "Cooldown": "перезарядка", "Jumping": "прыжок",
    "Persistent": "постоянный эффект", "Buff": "баф", "Minion": "приспешники", "CreatesMinion": "создаёт приспешников",
    "IceCrystal": "ледяной кристалл", "Totem": "тотем", "Trap": "ловушка", "Channel": "поддержание",
    "Chains": "цепь", "Aura": "аура", "Herald": "вестник", "AppliesCurse": "проклятие", "Nova": "кольцо",
    "Sustained": "длительное действие", "CreatesGroundEffect": "эффект на земле", "Trigger": "срабатывание",
    "Triggered": "срабатывающее", "Physical": "физический", "Fire": "огонь", "Cold": "холод",
    "Lightning": "молния", "Chaos": "хаос", "Movement": "перемещение", "Barrageable": "залп",
    "UsableWhileMoving": "на ходу", "Shapeshift": "превращение", "Ammunition": "боеприпасы",
}


def _inflict(forms: str) -> str:
    """"inflicts Freeze", "chance to Shock", "Shocks enemies": creating an ailment (a gem that merely mentions it,
    like "Ignite applied to you" or "culling a Shocked enemy", does not)."""
    return rf"(?:inflict\w*|chance to|apply|applies|causes?) .{{0,20}}\b(?:{forms})\b|\b(?:{forms}) (?:nearby )?enem"


def _against(state: str) -> str:
    """"against Frozen enemies", "culling a Shocked enemy": needing an ailment on the enemy."""
    return rf"(?:against|culling|hitting|hit|on|to) (?:an? |the )?{state} (?:enem|target)|{state} enem\w* hit by"


@dataclass(frozen=True)
class Mechanic:
    key: str
    name: str  # as the Russian client calls it
    explain: str  # what a beginner needs to know, one or two sentences
    creates: str  # regex over a gem's description and stat ids: the gem creates or inflicts it
    uses: str  # the gem uses it up or needs it
    created_by_tags: tuple = ()  # gem tags that create it (every cold hit builds Freeze)
    used_by_tags: tuple = ()  # gem tags that use it (every attack hit consumes an Impale)
    blocks: str = ""  # the gem is kept from using it
    prevents: str = ""  # the gem cannot create it (Glacial Cascade: "never_freeze")


MECHANICS = [
    Mechanic("impale", "Прокол",
             "Прокалывающий удар запоминает 30% своего урона; следующий удар атакой по этому врагу снимает Прокол и "
             "наносит этот урон ещё раз как физический.",
             r"impale_on_hit|impale_chance|inflicts? impale|impales? enemies|explosion_impale",
             r"consum\w* (?:the |an? )?impale|impale\w* .{0,30}consum", used_by_tags=("attack",),
             blocks=r"cannot_consume_impale"),
    Mechanic("ice_crystal", "Ледяной кристалл",
             "Кристалл стоит на земле и разбивается уроном — твоим или врагов; при разрушении взрывается холодом. "
             "Разбить его может любой твой удар.",
             r"\bice crystals?\b.{0,60}(?:call forth|create|wall)|(?:create|call forth)\w* .{0,40}ice crystal|"
             r"ice_crystal_maximum_life",
             r"hit an ice crystal|ice crystals? .{0,40}(?:explode|shatter)"),
    Mechanic("freeze", "Заморозка",
             "Урон от холода копит шкалу заморозки врага; когда она заполнится, враг заморожен. Скиллы, которые её "
             "«поглощают», снимают заморозку ради усиленного удара.",
             _inflict("freeze|freezes|freezing") + r"|freeze[_ ]buildup|hypothermia",
             r"consum\w* .{0,30}freeze|freeze is consumed|" + _against("frozen"),
             created_by_tags=("cold",), prevents=r"never_freeze|cannot_freeze"),
    Mechanic("shock", "Шок",
             "Урон от молнии может наложить шок — враг получает больше урона. Некоторые скиллы поглощают шок ради "
             "дополнительного эффекта.",
             _inflict("shock|shocks|shocking") + r"|shock chance|chance to shock", r"consum\w* .{0,30}shock|" + _against("shocked"), created_by_tags=("lightning",)),
    Mechanic("ignite", "Поджог",
             "Урон от огня может поджечь врага — он получает урон огнём со временем.",
             _inflict("ignite|ignites|igniting"), r"consum\w* .{0,30}ignit|" + _against("ignited"), created_by_tags=("fire",)),
    Mechanic("bleed", "Кровотечение",
             "Физический урон может наложить кровотечение — урон со временем, сильнее, когда враг двигается.",
             _inflict("bleed|bleeds|bleeding") + r"|cause_bleeding|bleed_on_hit",
             r"consum\w* .{0,30}bleed|" + _against("bleeding")),
    Mechanic("poison", "Отравление", "Отравление наносит урон хаосом со временем; яды складываются.",
             _inflict("poison|poisons|poisoning") + r"|poison_on_hit", r"consum\w* .{0,30}poison|" + _against("poisoned")),
    Mechanic("frenzy", "Заряды ярости",
             "Заряды ярости дают скорость и урон, пока есть; некоторые скиллы тратят их на усиленный эффект.",
             r"gain\w* .{0,30}frenzy charge|frenzy_charge_on|grant\w* .{0,20}frenzy charge",
             r"consum\w* .{0,40}frenzy charge"),
    Mechanic("power", "Заряды энергии",
             "Заряды энергии усиливают критические удары; некоторые скиллы тратят их на усиленный эффект.",
             r"gain\w* .{0,30}power charge|power_charge_on|grant\w* .{0,20}power charge",
             r"consum\w* .{0,40}power charge"),
    Mechanic("endurance", "Заряды выносливости",
             "Заряды выносливости дают защиту; некоторые скиллы тратят их на усиленный эффект.",
             r"gain\w* .{0,30}endurance charge|endurance_charge_on|grant\w* .{0,20}endurance charge",
             r"consum\w* .{0,40}endurance charge"),
    Mechanic("rage", "Свирепость",
             "Свирепость копится от ударов и усиливает атаки; некоторые скиллы расходуют её ради сильного удара.",
             r"gain\w* .{0,20}\brage\b|\brage_on_|grants? \brage\b|rage_regen",
             r"consum\w* .{0,30}\brage\b|spend\w* .{0,20}\brage\b|\brage spent|\brage_cost|uses? \d* ?rage"),
    Mechanic("infusion", "Насыщение",
             "Насыщения появляются, когда подбираешь остатки стихий; скиллы, которые их поглощают, получают "
             "дополнительный эффект.",
             r"\bremnants?\b|gain\w* .{0,30}infusion", r"consum\w* .{0,40}infusion"),
    Mechanic("armour_break", "Разрушение брони",
             "Скиллы, разрушающие броню, снижают броню врага; при полном разрушении враг получает больше "
             "физического урона, а некоторые скиллы и поддержки срабатывают именно на это.",
             r"break\w* .{0,20}armour|armour_break|armour_explosion", r"fully (?:broken|break)\w* armour"),
    Mechanic("glory", "Слава", "Слава копится от ударов и тратится на особо мощные скиллы.",
             r"gain\w* .{0,20}glory|glory_on", r"consum\w* .{0,30}glory|require\w* .{0,20}glory|glory_cost"),
    Mechanic("combo", "Комбо",
             "Комбо копится от успешных ударов другими скиллами; скиллы, которым нужно Комбо, тратят его на мощный "
             "удар, когда оно набрано.",
             r"gain\w* .{0,20}\bcombo", r"consum\w* .{0,30}combo|combo finisher|required_number_of_combo|"
             r"maximum combo", created_by_tags=("attack",)),
    Mechanic("heavy_stun", "Тяжёлое оглушение",
             "Урон копит шкалу оглушения; при её заполнении враг тяжело оглушён — некоторые скиллы наносят по таким "
             "врагам особый урон.",
             r"build\w* up stun|stun_threshold|hit_damage_stun_multiplier", _against("heavy stunned")),
    Mechanic("shapeshift", "Превращение",
             "Скиллы превращения меняют облик героя (медведь, виверна, волк); некоторые предметы и пассивки "
             "работают только в превращённом облике.",
             r"(?<![\w-])shapeshift(?:ing)?(?![\w-])", r"\bshapeshifted\b|while in (?:bear|wyvern|wolf|werewolf) form"),
]
# The game's own explanation of each mechanic (its term popups, poe2lab.keywords), shown instead of ours when the
# game data is unpacked.
MECHANIC_TERMS = {"impale": ["Impale"], "ice_crystal": ["IceCrystals", "IceCrystalShatter"],
                  "freeze": ["Freeze", "PrimedFreeze"], "shock": ["Shock"], "ignite": ["Ignite"],
                  "bleed": ["Bleeding"], "poison": ["Poison"], "frenzy": ["Charges"], "power": ["Charges"],
                  "endurance": ["Charges"], "rage": ["Rage"], "infusion": ["ElementalInfusion"],
                  "armour_break": ["ArmourBreak"], "glory": ["Glory"], "combo": ["Combo"],
                  "heavy_stun": ["HeavyStun", "PrimedStun"], "shapeshift": ["Shapeshift"]}


def _text(gem: dict) -> str:
    """Description, stat ids and skill types ("Shapeshift" is a type of the bear and wyvern skills)."""
    return " ".join([gem.get("description", ""), *gem.get("stats", []), *gem.get("types", [])]).lower()


def mechanics_of(gem: dict) -> dict[str, list[str]]:
    """{"creates": [...keys], "uses": [...keys]} for one gem."""
    text, tags = _text(gem), set(gem.get("tags", []))
    out = {"creates": [], "uses": []}
    for m in MECHANICS:
        blocked = bool(m.blocks and re.search(m.blocks, text))
        # a damage type creates ailments for the skills that deal it, not for supports tagged with it
        uses = not blocked and (re.search(m.uses, text) or (not gem["support"] and tags & set(m.used_by_tags)))
        prevented = bool(m.prevents and re.search(m.prevents, text))
        # by damage type or skill kind only a gem that does not itself spend it (Tempest Bell spends Combo, the
        # other attacks build it)
        by_tags = not gem["support"] and tags & set(m.created_by_tags) and not re.search(m.uses, text)
        if not prevented and (re.search(m.creates, text) or by_tags):
            out["creates"].append(m.key)
        if uses:
            out["uses"].append(m.key)
    return out


def links(groups: list[dict], items: list[dict] = ()) -> list[dict]:
    """Mechanics that one gem or unique item of the build creates and another uses; and mechanics a skill needs
    that nothing in the build creates."""
    by = {m.key: m for m in MECHANICS}
    creators, users = {}, {}
    for it in items:
        ref = {"gem": it["name"], "skill": it["slot"], "group": None, "support": True, "item": True}
        for key in it["mechanics"]["creates"]:
            creators.setdefault(key, []).append(ref)
        for key in it["mechanics"]["uses"]:
            users.setdefault(key, []).append(ref)
    for g in groups:
        if not g["enabled"]:
            continue
        main = g["actives"][0]["name"] if g["actives"] else ""
        for gem in g["gems"]:
            if not gem["enabled"]:
                continue
            owner = main if gem["support"] else gem["name"]
            ref = {"gem": gem["name"], "skill": owner, "group": g["index"], "support": gem["support"]}
            for key in gem["mechanics"]["creates"]:
                creators.setdefault(key, []).append(ref)
            for key in gem["mechanics"]["uses"]:
                users.setdefault(key, []).append(ref)
    out = []
    for key in sorted(set(creators) | set(users), key=lambda k: [m.key for m in MECHANICS].index(k)):
        c, u = creators.get(key, []), users.get(key, [])
        # a link is two different gems; a mechanic only created (or only used) is a warning, not a link
        if c and u and ({r["gem"] for r in c} | {r["gem"] for r in u}) != {r["gem"] for r in c} & {r["gem"] for r in u}:
            out.append({"key": key, "name": by[key].name, "explain": by[key].explain, "creates": c, "uses": u,
                        "terms": MECHANIC_TERMS.get(key, [])})
        elif u and not c and not by[key].used_by_tags and any(not r["support"] for r in u):
            out.append({"key": key, "name": by[key].name, "explain": by[key].explain, "creates": [], "uses": u,
                        "missing": True, "terms": MECHANIC_TERMS.get(key, [])})
    return out


def available_level(gem: dict) -> int | None:
    """Rough character level from which a gem can be had while levelling (area level ~ character level); None for
    gems that do not come from uncut gems (weapon skills, lineage supports)."""
    tier = gem.get("tier") or 0
    if tier <= 0:
        return None
    if gem["support"]:
        return UNCUT_SUPPORT_AREA.get(tier)
    return max(gem.get("reqLevel") or 0, UNCUT_SKILL_AREA.get(tier, 62))


def _own_dps(engine, config, group: int) -> float:
    return engine.what_if(config=config, main_socket_group=group).get("CombinedDPS", 0.0)


def _measure_group(engine, config, g: dict) -> int | None:
    """Whose DPS a support in this group moves: the group's own skill if it deals damage, else the main skill."""
    return g["index"] if g["enabled"] and _own_dps(engine, config, g["index"]) > 0 else None


def build_view(engine, config: dict, mechanics_raw: dict | None = None, uniques: list[dict] = (),
               item_gaps: list[dict] = ()) -> dict:
    """Every socket group with its gems, what each support is worth, the unique items and the mechanics they take
    part in, and the links between all of them. `uniques` and `item_gaps` come from poe2lab.knowledge."""
    groups = engine.skill_groups()
    local = {}
    for s in (mechanics_raw or {}).get("skills", []):
        local[(s["group"], s["name"])] = {
            "lines": list(dict.fromkeys(l for st in s["statSets"] for l in st["lines"])),
            "linesLocal": list(dict.fromkeys(l for st in s["statSets"] for l in st.get("linesLocal", []))),
            "unseen": [u.get("textLocal") or u.get("text") or [u["stat"]] for st in s["statSets"]
                       for u in st["unmapped"] if u["value"]]}
    for g in groups:
        measure = _measure_group(engine, config, g)
        g["measured"] = "own" if measure else "main"
        base = engine.what_if(config=config, main_socket_group=measure) if measure else engine.what_if(config=config)
        for gem in g["gems"]:
            gem["mechanics"] = mechanics_of(gem)
            gem["available"] = available_level(gem)
            gem["because"] = sorted({TYPE_RU.get(t, t) for f in gem["fits"] for t in f["because"]})
            gem.update(local.get((g["index"], gem["name"]), {"lines": [], "linesLocal": [], "unseen": []}))
            gem["unseen"] = [" / ".join(u) if isinstance(u, list) else u for u in gem["unseen"]][:4]
            gem["terms"] = kw.find([gem["description"], *gem["lines"]])
            if gem["support"] and gem["enabled"] and g["enabled"]:
                without = engine.what_if(config=config, disable_gems=[(g["index"], gem["index"])],
                                         main_socket_group=measure)
                gem["worth"] = {k: -v for k, v in metric_changes(without, base).items()}
            else:
                gem["worth"] = None
        for a in g["actives"]:
            a["typesRu"] = [TYPE_RU[t] for t in a["types"] if t in TYPE_RU]
    items = []
    for u in uniques:
        item = {"name": u["name"], "slot": u["slot"], "lines": u["lines"], "description": " ".join(u["lines"]),
                "support": True, "enabled": True}
        item["mechanics"] = mechanics_of(item)
        item["terms"] = kw.find(u["lines"])
        prefix = u["name"].split(",")[0]
        item["unseen"] = [g["text_local"] or g["text"] for g in item_gaps if g["where"].startswith(prefix)][:6]
        items.append(item)
    created = {k for g in groups if g["enabled"] for x in g["gems"] if x["enabled"] for k in x["mechanics"]["creates"]}
    created |= {k for it in items for k in it["mechanics"]["creates"]}
    generic = {m.key for m in MECHANICS if m.used_by_tags}
    for g in groups:
        for x in g["gems"]:
            x["mechanics"]["uses"] = [k for k in x["mechanics"]["uses"] if k not in generic or k in created]
    found = links(groups, items)
    terms = {t for g in groups for x in g["gems"] for t in x["terms"]} | {t for it in items for t in it["terms"]}
    terms |= {t for l in found for t in l["terms"]}
    return {"groups": groups, "items": items, "links": found, "terms": kw.entries(terms),
            "mechanics": {m.key: {"name": m.name, "explain": m.explain} for m in MECHANICS}}


def leveling_view(engine, config: dict, groups: list[dict] | None = None) -> dict:
    """When each gem of the build can be had, and for each damaging skill the supports to use at each stage of
    levelling - the build's own when available, otherwise the best alternatives PoB finds (several, to choose)."""
    groups = groups or engine.skill_groups()
    timeline = {}
    plans = []
    for g in groups:
        if not g["enabled"] or not g["actives"]:
            continue
        skill = next((x for x in g["gems"] if not x["support"]), None)
        for gem in g["gems"]:
            gem["available"] = available_level(gem)
            if gem["available"] is not None:
                at = timeline.setdefault(gem["available"], {})
                entry = at.setdefault(gem["name"], {"name": gem["name"], "support": gem["support"], "skills": []})
                if g["actives"][0]["name"] not in entry["skills"]:
                    entry["skills"].append(g["actives"][0]["name"])
        measure = _measure_group(engine, config, g)
        if not measure:
            continue  # a buff or utility group: its supports are listed in the timeline, nothing to rank
        candidates = engine.support_candidates(g["index"])
        gains = engine.support_gains(g["index"], [c["id"] for c in candidates], config, measure_group=measure)
        base = gains["base"]["dps"] or 1
        ranked = []
        for c in candidates:
            m = gains.get(c["id"])
            if m and m["dps"] > base * 1.005:
                ranked.append(c | {"dps": (m["dps"] / base - 1) * 100, "available": UNCUT_SUPPORT_AREA.get(c["tier"])})
        ranked.sort(key=lambda c: -c["dps"])
        own = [x for x in g["gems"] if x["support"]]
        stages = []
        for level in SUPPORT_STAGES:
            have = [x["name"] for x in own if x["available"] is not None and x["available"] <= level]
            later = [x["name"] for x in own if x["available"] is None or x["available"] > level]
            # always a few to choose from: free sockets while the build's own supports are missing, and variety
            options, families = [], set()
            for c in ranked:  # one per family: "Accuracy II" replaces "Accuracy I" once it drops
                if c["available"] <= level and (c["family"] or c["name"]) not in families:
                    families.add(c["family"] or c["name"])
                    options.append(c)
            options = options[:OPTIONS]
            stages.append({"level": level, "build": have, "later": later,
                           "options": [{"name": c["name"], "dps": c["dps"], "tier": c["tier"],
                                        "because": sorted({TYPE_RU.get(t, t) for t in c["because"]})}
                                       for c in options]})
        # collapse stages that change nothing
        compact = [s for i, s in enumerate(stages) if i == 0 or (s["build"], [o["name"] for o in s["options"]]) !=
                   (stages[i - 1]["build"], [o["name"] for o in stages[i - 1]["options"]])]
        plans.append({"group": g["index"], "skill": g["actives"][0]["name"], "main": g["main"],
                      "skillAvailable": skill and skill["available"], "slots": len(own), "stages": compact})
    return {"timeline": [{"level": lv, "gems": sorted(timeline[lv].values(), key=lambda x: (x["support"], x["name"]))}
                         for lv in sorted(timeline)], "plans": plans,
            "uncutSkillArea": UNCUT_SKILL_AREA, "uncutSupportArea": UNCUT_SUPPORT_AREA}
