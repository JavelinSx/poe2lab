"""A prompt for any chat AI, for a player with no API key: the build and PoB's numbers, ready to paste with the
question into ChatGPT, DeepSeek, Claude or Gemini, even into their free web chats.

A web chat cannot call poe2lab's tools. So the reports the assistant would call for the question's topic go into the
prompt, computed beforehand. The topic is guessed by the question's words:
- damage: the build report and what each stat gives;
- defence and gear: the build report, plus what each stat gives for gear;
- the tree: the passives within reach;
- the guide: the character against its target.

Two sizes:
- compact: the key numbers, the skills, the gear, the taken notables, a trimmed report. For free chats with short
  messages.
- full: everything the assistant itself starts with, and the whole reports.

The question comes first and again at the end, so a long prompt does not lose it."""
import json

from ..knowledge import collect as collect_mechanics
from ..profile import describe as describe_profile
from .agent import STYLES, build_context
from .tools import Toolbox

TOPICS = {
    "damage": (("урон", "дпс", "dps", "damage", "крит", "crit", "скилл", "skill", "бьёт", "бьет", "убива", "босс",
                "boss", "clear", "клир"), ("build_report", "stat_values")),
    "defence": (("защит", "выжив", "умира", "смерт", "ваншот", "сопротив", "резист", "ehp", "жизн", "здоров",
                 "энергощит", "броня", "брони", "уклон", "хаос", "defen", "surviv", "die ", "dying", "resist",
                 "life", "armour", "evasion"), ("build_report",)),
    "tree": (("дерев", "пассив", "нод", "узел", "узл", "очк", "возвыш", "respec", "passive", "tree", "node",
              "ascend"), ("tree_options",)),
    "gear": (("шмот", "вещ", "предмет", "крафт", "слот", "кольц", "амулет", "шлем", "ботин", "сапог", "перчат",
              "пояс", "оруж", "щит", "рун", "gear", "item", "craft", "ring", "amulet", "helmet", "boots", "gloves",
              "belt", "weapon", "rune"), ("build_report", "stat_values")),
    "target": (("гайд", "цел", "guide", "target"), ("target_report",)),
}
ORDER = ("build_report", "stat_values", "tree_options", "target_report")
REPORTS = {
    "ru": {
        "build_report": "Отчёт билда: что сломано (gates), какие удары персонаж переживает (baseline), вилка урона, "
                        "сопротивления, какие моды полезнее всего (ranking) и путь улучшений по шагам (path)",
        "stat_values": "Сколько даёт каждый стат, если добавить его на персонажа: % к урону (dps), к эффективному "
                       "здоровью (ehp) и к переживаемым ударам по типам",
        "tree_options": "Пассивки в пределах 6 очков: польза на очко с учётом пути (growth) и что можно "
                        "перераспределить (respec)",
        "target_report": "Персонаж сейчас против цели — гайда, по которому он играет",
    },
    "en": {
        "build_report": "Build report: what is broken (gates), the hits the character survives (baseline), the damage "
                        "range, resistances, the most useful mods (ranking) and the upgrade path step by step (path)",
        "stat_values": "What each stat gives when added to the character: % damage (dps), effective life (ehp) and "
                       "survivable hits by type",
        "tree_options": "Passives within 6 points: value per point with the path (growth), what can be respecced "
                        "(respec)",
        "target_report": "The character now against its target, the guide it follows",
    },
}
RULES = {
    "ru": """Ты — опытный игрок и аналитик билдов Path of Exile 2 (патч 0.5). Ниже мой вопрос и данные моего билда.
Их посчитал Path of Building (PoB) в программе poe2lab. Отвечай по-русски.

Как отвечать:
1. Цифры бери только из данных ниже. Если нужной цифры нет, так и скажи или пометь «(оценка)». Не выдумывай моды,
   базы и механики.
2. Механику выводи из описаний скиллов и предметов. Раздел «PoB не считает» — то, чего нет в цифрах PoB.
3. Факты из профиля билда подтверждены мной: доверяй им больше, чем цифрам PoB.
4. Предметы с порчей («испорчен», corrupted) изменить нельзя, для них только «что искать в замене».
5. Если билд построен вокруг механики (крит, заряды и т. п.), не советуй от неё отказываться по снимку персонажа
   сейчас.
6. Названия пиши так, как в русском клиенте игры (официальные названия — в данных ниже).
7. Отвечай только по Path of Exile 2.""",
    "en": """You are an experienced player and build analyst of Path of Exile 2 (patch 0.5). Below are my question and
my build's data, computed by Path of Building (PoB) in poe2lab. Answer in English.

How to answer:
1. Take numbers only from the data below. If a number is not there, say so or mark it "(estimate)". Do not invent
   mods, bases or mechanics.
2. Work out mechanics from the skill and item texts. "PoB does not count" lists what is not in PoB's numbers.
3. The build profile's facts are confirmed by me: trust them over PoB's numbers.
4. Corrupted items cannot be changed: for them only "what to look for in a replacement".
5. If the build is built around a mechanic (crit, charges...), do not advise dropping it on a snapshot of the
   character now.
6. Answer about Path of Exile 2 only.""",
}
HEAD = {"ru": ("Мой вопрос", "Правила ответа", "Билд", "Расчёты PoB по теме вопроса", "Ещё раз мой вопрос"),
        "en": ("My question", "How to answer", "The build", "PoB's reports for the question", "My question again")}
STAT_KEYS = [("CombinedDPS", "DPS основного скилла", "main skill DPS"), ("Life", "здоровье", "life"),
             ("EnergyShield", "энергощит", "energy shield"), ("Mana", "мана", "mana"), ("Armour", "броня", "armour"),
             ("Evasion", "уклонение", "evasion"), ("TotalEHP", "эффективное здоровье (EHP)", "effective life (EHP)"),
             ("FireResist", "сопр. огню", "fire res"), ("ColdResist", "сопр. холоду", "cold res"),
             ("LightningResist", "сопр. молнии", "lightning res"), ("ChaosResist", "сопр. хаосу", "chaos res"),
             ("PhysicalMaximumHitTaken", "переживаемый физ. удар", "max physical hit"),
             ("ChaosMaximumHitTaken", "переживаемый удар хаосом", "max chaos hit"),
             ("CritChance", "шанс крита главного скилла, %", "main skill crit chance, %"),
             ("CritMultiplier", "множитель крита главного скилла", "main skill crit multiplier")]


def topics_of(question: str) -> list[str]:
    q = question.lower()
    return [name for name, (words, _) in TOPICS.items() if any(w in q for w in words)]


def reports_for(topics: list[str], has_target: bool) -> list[str]:
    wanted = {r for t in topics for r in TOPICS[t][1]}
    if not has_target:
        wanted.discard("target_report")
    return [r for r in ORDER if r in (wanted or {"build_report"})]  # no topic: the build report answers most


METRIC_DICTS = ("percentChange", "changes", "one")  # the % changes of the metrics: zeros say nothing


def _lean(data):
    """Numbers rounded (1 decimal, 2 below 1) and the zero changes of metric dicts left out: shorter, same sense."""
    if isinstance(data, float):
        return round(data, 1 if abs(data) >= 1 else 2)
    if isinstance(data, list):
        return [_lean(x) for x in data]
    if isinstance(data, dict):
        return {k: ({m: _lean(v) for m, v in x.items() if not (isinstance(v, (int, float)) and abs(v) < 0.05)}
                    if k in METRIC_DICTS and isinstance(x, dict) else _lean(x)) for k, x in data.items()}
    return data


def _trim(name: str, data):
    """A report cut to what a short chat message can hold."""
    if name == "build_report" and isinstance(data, dict):
        keep = {k: data[k] for k in ("gates", "baseline", "damageRange", "resistances") if k in data}
        keep["ranking"] = (data.get("ranking") or [])[:6]
        keep["path"] = (data.get("path") or [])[:4]
        return keep
    if name == "stat_values" and isinstance(data, list):
        return sorted(data, key=lambda r: -max(abs(v) for v in r["percentChange"].values()))[:12]
    if name == "tree_options" and isinstance(data, dict):
        return {"growth": data.get("growth", [])[:6], "respec": data.get("respec", [])[:4]}
    return data


def compact_context(engine, bp, glossary: dict | None, config: dict, lang: str = "ru") -> str:
    """The build in a few thousand characters: who, the key numbers, damage by skill, the confirmed profile, skills
    with their supports, the gear with its mods, the taken notables, what PoB does not count, official names."""
    ru = lang != "en"
    info, stats = engine.info(), engine.what_if(config=config)
    out = [(f"{info['class']} / {info['ascendancy'] or ('без возвышения' if ru else 'no ascendancy')}, "
            f"{info['level']} {'ур.' if ru else 'level'}, {'основной скилл' if ru else 'main skill'}: {engine.main_skill()}")]
    num = lambda v: (f"{v:,.0f}".replace(",", " " if ru else ",") if abs(v) >= 100 else f"{v:.1f}")  # noqa: E731
    nums = [f"{label_ru if ru else label_en}: {num(stats[k])}" for k, label_ru, label_en in STAT_KEYS
            if stats.get(k) is not None]
    out.append(("Ключевые цифры (PoB): " if ru else "Key numbers (PoB): ") + "; ".join(nums))
    damage = [d for d in engine.skill_damage(config) if d["dps"] > 0][:6]
    if damage:
        out.append(("Урон и шанс крита по скиллам, если сделать скилл основным (крит у каждого скилла свой): " if ru
                    else "Damage and crit chance per skill as the main one (crit is each skill's own): ")
                   + "; ".join(f"{d['name']} {num(d['dps'])}, {'крит' if ru else 'crit'} {d['crit']:.0f}%" for d in damage))
    out.append(("Профиль билда (подтверждено мной): " if ru else "Build profile (confirmed by me): ")
               + "; ".join(describe_profile(bp)))
    groups = []
    for g in engine.skill_groups():
        actives = [x["name"] for x in g["gems"] if not x["support"]]
        supports = [x["name"] for x in g["gems"] if x["support"]]
        if actives:
            groups.append(", ".join(actives) + (f" ← {', '.join(supports)}" if supports else ""))
    out.append(("Скиллы (← саппорты):\n" if ru else "Skills (← supports):\n") + "\n".join(f"- {s}" for s in groups))
    items = []
    for i in engine.equipped_item_details():
        lines = [l["line"] for k in ("implicit", "runes", "explicit") for l in i[k]]
        mark = (" [испорчен]" if ru else " [corrupted]") if i["corrupted"] else ""
        items.append(f"- {i['slot']}: {i['name']}{mark} — " + "; ".join(lines))
    out.append(("Надетые предметы и их моды:\n" if ru else "Equipped items and their mods:\n") + "\n".join(items))
    notables = [n["name"] for n in engine.allocated_nodes() if n["type"] in ("Notable", "Keystone")]
    out.append(("Взятые значимые и ключевые пассивки: " if ru else "Allocated notables and keystones: ")
               + ", ".join(notables))
    gaps = collect_mechanics(engine).gaps[:12]
    if gaps:
        out.append(("PoB не считает:\n" if ru else "PoB does not count:\n") + "\n".join(f"- {g.where}: {g.text}" for g in gaps))
    if glossary:
        out.append("Официальные русские названия: " + "; ".join(f"{k} = {v}" for k, v in sorted(glossary.items())))
    return "\n\n".join(out)


def make(engine, bp, profile, db, question: str, *, size: str = "compact", style: str = "short", lang: str = "ru",
         glossary: dict | None = None, target: dict | None = None, target_text: str | None = None) -> dict:
    """The prompt: {"prompt", "chars", "topics", "reports"}. size: compact | full; style: short | detailed (the
    assistant's answer formats); target: the build's guide for the target report (poe2lab.assistant.Toolbox)."""
    lang = "en" if lang == "en" else "ru"
    question = question.strip()
    config = profile.config()
    topics = topics_of(question)
    names = reports_for(topics, target is not None)
    tools = Toolbox(engine, profile, db, target)
    blocks = []
    for name in names:
        data = json.loads(tools.call(name, {}))
        data = _lean(data if size == "full" else _trim(name, data))
        blocks.append(f"{name} — {REPORTS[lang][name]}:\n{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}")
    build = (build_context(engine, bp, glossary, config, target_text) if size == "full"
             else compact_context(engine, bp, glossary, config, lang))
    rules = RULES[lang] + ("\n\n" + STYLES.get(style, STYLES["short"]).replace("из инструментов", "из данных")
                           if lang == "ru" else "")
    q, r, b, p, again = HEAD[lang]
    text = "\n\n".join([f"=== {q} ===\n{question}", f"=== {r} ===\n{rules}", f"=== {b} ===\n{build}",
                        f"=== {p} ===\n" + "\n\n".join(blocks), f"=== {again} ===\n{question}"])
    return {"prompt": text, "chars": len(text), "topics": topics, "reports": names}
