"""The build's target - a guide at its end game, chosen in the build profile - next to the character now: where each
gets its power, so advice can tell what matters at this stage from what the build maxes later (crit that pays little
at level 28 is half of the guide's damage at 98).

"Where the power comes from": the allocated passives grouped by what they give (crit, speed, elemental damage,
energy shield...); each group is taken away in PoB and the loss of damage and effective life is its worth."""
import re

from .gradients import metric_changes

# what a passive gives, by its lines; a node may count in several groups
GROUPS = [
    ("crit", "крит", r"Critical"),
    ("speed", "скорость атаки и чар", r"(Attack|Cast|Skill) Speed"),
    ("elemental", "урон стихий", r"(Elemental|Cold|Fire|Lightning) Damage|Damage as Extra (Cold|Fire|Lightning)"),
    ("physical", "физический урон", r"Physical Damage"),
    ("chaos", "урон хаосом", r"Chaos Damage"),
    ("attack", "урон атак", r"Attack Damage|Damage with Attacks|Melee Damage|increased Damage\b"),
    ("spell", "урон чар", r"Spell Damage"),
    ("ailments", "состояния (поджог, шок, заморозка, кровотечение, яд)", r"Ignite|Shock|Freeze|Chill|Bleed|Poison"),
    ("charges", "заряды", r"Charge"),
    ("minion", "приспешники", r"Minion"),
    ("life", "здоровье", r"maximum Life|Life Regeneration|Leech"),
    ("es", "энергощит", r"Energy Shield"),
    ("evasion", "уклонение", r"Evasion|Deflect"),
    ("armour", "броня", r"Armour"),
    ("block", "блок", r"Block"),
    ("resist", "сопротивления", r"Resistance"),
]
MIN_NODES = 3  # a group of fewer passives is not an investment
KEYS = ("CombinedDPS", "CritChance", "CritMultiplier", "Speed", "HitChance", "Life", "EnergyShield", "Evasion",
        "Armour", "TotalEHP", "FireResist", "ColdResist", "LightningResist", "ChaosResist")


def investments(engine, config: dict) -> list[dict]:
    """The passive groups the build invests in, most valuable first: how many passives and what taking them all away
    costs (damage and effective life, %)."""
    graph = engine.tree_graph()
    # keystones change how the build works (Hollow Palm: attacks without a weapon) - taking one away is not "less
    # crit" but another build; they are listed on their own
    taken = [n for n in graph["nodes"] if n["alloc"] and not n["asc"]
             and n["type"] not in ("ClassStart", "AscendClassStart", "Keystone")]
    base = engine.what_if(config=config)
    out = []
    for key, label, rx in GROUPS:
        ids = [n["id"] for n in taken if any(re.search(rx, l) for l in n["stats"])]
        if len(ids) < MIN_NODES:
            continue
        changes = metric_changes(engine.what_if(config=config, remove_nodes=ids), base)
        out.append({"key": key, "label": label, "nodes": len(ids), "dps": changes.get("dps", 0.0),
                    "ehp": changes.get("ehp", 0.0)})
    return sorted(out, key=lambda g: -(abs(g["dps"]) + abs(g["ehp"])))


def summary(engine, config: dict, name: str = "") -> dict:
    """One build as the assistant compares it: level, main skill, key numbers, where the power comes from, the
    ascendancy and keystones."""
    info = engine.info()
    stats = engine.what_if(config=config)
    nodes = engine.allocated_nodes()
    return {"name": name, "level": info["level"], "class": info["class"], "ascendancy": info["ascendancy"],
            "mainSkill": engine.main_skill(), "stats": {k: stats.get(k) for k in KEYS},
            "investments": investments(engine, config),
            "ascendancyNotables": [n["name"] for n in nodes if n["ascendancy"] and n["type"] == "Notable"],
            "notables": sorted(n["name"] for n in nodes if not n["ascendancy"] and n["type"] == "Notable"),
            "keystones": [n["name"] for n in nodes if n["type"] == "Keystone"],
            "skills": [{"name": s["name"], "dps": s["dps"]} for s in engine.skill_damage(config)[:6]]}


def _line(s: dict) -> str:
    st = s["stats"]
    parts = [f"{s['class']} / {s['ascendancy'] or 'без возвышения'}, {s['level']} ур., основной скилл {s['mainSkill']}",
             f"DPS {st['CombinedDPS'] or 0:,.0f}", f"крит {st['CritChance'] or 0:.1f}% ×{st['CritMultiplier'] or 0:.2f}",
             f"скорость {st['Speed'] or 0:.2f}/с", f"здоровье {st['Life'] or 0:,.0f}", f"энергощит {st['EnergyShield'] or 0:,.0f}",
             f"EHP {st['TotalEHP'] or 0:,.0f}"]
    return ", ".join(parts)


def _power(s: dict) -> str:
    return "; ".join(f"{g['label']} — {g['nodes']} пассивок, без них урон {g['dps']:+.0f}%, EHP {g['ehp']:+.0f}%"
                     for g in s["investments"][:6]) or "нет групп из 3+ пассивок"


def context_text(now: dict, target: dict) -> str:
    """The two pictures side by side, for the assistant's context."""
    lines = [
        f"Цель билда (эталон, выбран игроком): «{target['name']}» — {_line(target)}.",
        f"Сила цели в дереве: {_power(target)}.",
        f"Возвышение цели: {', '.join(target['ascendancyNotables']) or '—'}; ключевые пассивки: "
        f"{', '.join(target['keystones']) or '—'}.",
        f"Значимые пассивки цели ({len(target['notables'])}) — у персонажа уже взяты: "
        f"{', '.join(n for n in target['notables'] if n in now['notables']) or '—'}; ещё нет: "
        f"{', '.join(n for n in target['notables'] if n not in now['notables']) or '—'}.",
        f"Значимые пассивки персонажа, которых нет у цели: "
        f"{', '.join(n for n in now['notables'] if n not in target['notables']) or '—'}.",
        f"Сейчас: {_line(now)}.",
        f"Сила персонажа сейчас в дереве: {_power(now)}.",
        f"Возвышение сейчас: {', '.join(now['ascendancyNotables']) or '—'}.",
    ]
    if target["mainSkill"] != now["mainSkill"]:
        lines.append(f"Основной скилл у цели — {target['mainSkill']}, у персонажа выбран {now['mainSkill']}.")
    return "\n".join(lines)
