"""One report for a build: what must be fixed, where to invest for a goal, and a step-by-step upgrade path."""
from dataclasses import asdict, dataclass

from ..knowledge import collect as collect_mechanics
from . import attributes as attrs
from .conditions import audit as audit_conditions
from .conditions import damage_range
from .gradients import Gradient, compute, hit_change, recovery_per_second
from .stats import mod_line
from .threats import DAMAGE_TYPES, MapProfile, recovery, survivable_hits

HIT_METRIC = {"Physical": "phys_hit", "Fire": "fire_hit", "Cold": "cold_hit", "Lightning": "lightning_hit",
              "Chaos": "chaos_hit"}
RES_CAP = 75
RES_BUFFER = 10
MIN_HIT_CHANCE = 90
WEAK_TYPE_SHARE = 0.5

# (damage, defence, recovery) weights of each goal
MODES = {
    "damage": (1.0, 0.25, 0.1),
    "balanced": (1.0, 1.0, 0.4),
    "defence": (0.25, 1.0, 0.5),
}


@dataclass
class Gate:
    level: str  # "must" (broken in game), "priority" (biggest gap), "warn"
    title: str
    detail: str


RES_NAMES = {"Fire": "огню", "Cold": "холоду", "Lightning": "молнии"}
HIT_NAMES = {"Physical": "физическим ударам", "Fire": "ударам огнём", "Cold": "ударам холодом",
             "Lightning": "ударам молнией", "Chaos": "ударам хаосом"}
ATTR_GENITIVE = {"Str": "силы", "Dex": "ловкости", "Int": "интеллекта"}
ATTR_NOMINATIVE = {"Str": "Сила", "Dex": "Ловкость", "Int": "Интеллект"}
ATTR_SHORT = {"Str": "силы", "Dex": "ловкости", "Int": "интеллекта"}


def _nodes_word(n: int) -> str:
    return "ноду" if n == 1 else "ноды" if n < 5 else "нод"


def attribute_gates(statuses, swaps, deps) -> list[Gate]:
    out = []
    for s in statuses:
        if s.margin < 0:
            fix = next((w for w in swaps if w.target == s.attr and w.all_met), None)
            how = (f"дешевле всего переключить {fix.nodes} атрибутную {_nodes_word(fix.nodes)} "
                   f"{ATTR_SHORT[fix.donor]} → {ATTR_SHORT[fix.target]} (DPS {fix.dps_pct:+.1f}%, жизнь {fix.life_pct:+.1f}%)"
                   if fix else f"добрать +{-s.margin:.0f} {ATTR_SHORT[s.attr]} с предмета")
            out.append(Gate("must", f"Не хватает {ATTR_GENITIVE[s.attr]}",
                            f"{s.have:.0f} из {s.need:.0f}, требуют: {', '.join(s.needed_by)}; {how}"))
        elif s.need > 0 and s.margin < attrs.LOW_MARGIN:
            holders = [d for d in deps if s.attr in d.provides]
            where = (f"держат предметы: {', '.join(d.slot for d in holders)}" if holders
                     else f"предметы его не дают, всё из дерева ({s.from_nodes} атрибутных нод)")
            out.append(Gate("warn", f"{ATTR_NOMINATIVE[s.attr]} на грани",
                            f"{s.have:.0f} из {s.need:.0f} (запас {s.margin:.0f}), нужно для: {', '.join(s.needed_by)}; {where}"))
    for d in deps:
        if d.breaks:
            lost = ", ".join(f"−{v:.0f} {ATTR_SHORT[a]}" for a, v in d.provides.items())
            out.append(Gate("warn", f"На предмете «{d.slot}» держатся требования",
                            f"снимешь {d.item} ({lost}) — перестанут работать: {', '.join(d.breaks)}"))
    return out


def zero_damage_gates(engine, stats: dict, config: dict) -> list[Gate]:
    """PoB cannot compute some skills (0 DPS for the main skill): say so and point at the skills that do damage,
    instead of ranking every mod by zero."""
    if stats.get("CombinedDPS", 0) >= 1:
        return []
    doing = [s for s in engine.skill_damage(config) if s["dps"] >= 1][:4]
    where = ("; ".join(f"«{s['name']}» (группа {s['group']}) — {s['dps']:,.0f}" for s in doing)
             if doing else "ни один скилл билда не даёт урона в PoB")
    return [Gate("must", f"PoB не считает урон основного скилла «{engine.main_skill()}»",
                 f"DPS 0 — оценки урона ниже ничего не значат. Урон есть у: {where}. Выберите основным скилл, "
                 "который реально наносит урон (список «Основной скилл» вверху)")]


def unread_gates(engine) -> list[Gate]:
    return [Gate("must", f"PoB не прочитал предмет «{u['slot']}»",
                 f"«{u['name']}» ({u['base']}): такой базы нет в текущей версии PoB — обычно это билд из прошлой "
                 f"версии игры. Всё посчитано без этого предмета; обновите его в билде")
            for u in engine.unread_items()]


def gates(stats: dict, hits: list, rec, mana_sustained: bool = False) -> list[Gate]:
    out = []
    for t in ("Fire", "Cold", "Lightning"):
        res, over = stats.get(f"{t}Resist", 0), stats.get(f"{t}ResistOverCap", 0)
        if res < RES_CAP:
            out.append(Gate("must", f"Резист к {RES_NAMES[t]} не в капе", f"{res:.0f}%, нужно ещё +{RES_CAP - res:.0f}%"))
        elif over < RES_BUFFER:
            out.append(Gate("warn", f"Резист к {RES_NAMES[t]} без запаса",
                            f"сверх капа {over:.0f}%: мод карты на снижение резистов опустит его ниже {RES_CAP}%"))
    chaos = stats.get("ChaosResist", 0)
    if chaos < RES_CAP:
        out.append(Gate("priority", "Хаос-резист ниже капа", f"{chaos:.0f}%, до капа +{RES_CAP - chaos:.0f}%"))
    if stats.get("SpiritUnreserved", 0) < 0:
        out.append(Gate("must", "Не хватает spirit", f"перерасход {-stats['SpiritUnreserved']:.0f}"))
    cost = stats.get("ManaPerSecondCost", 0)
    regain = stats.get("ManaRegenRecovery", 0) + stats.get("ManaLeechGainRate", 0) + stats.get("ManaOnHitRate", 0)
    if cost > regain and not mana_sustained:
        out.append(Gate("warn", "Основной скилл тратит больше маны, чем восстанавливается",
                        f"{cost:.0f}/с против {regain:.0f}/с (регенерация + похищение + за удар), дефицит {cost - regain:.0f}/с; "
                        "ману за убийство и флаконы PoB здесь не учитывает"))
    hit = stats.get("HitChance", 100)
    if hit < MIN_HIT_CHANCE:
        out.append(Gate("warn", "Низкий шанс попадания", f"{hit:.0f}%: точность — дешёвый урон"))
    finite = [h for h in hits if not h.immune]  # an immunity is not "the best type" to measure weakness against
    best = max((h.normal for h in finite), default=0)
    for h in finite:
        if h.normal < best * WEAK_TYPE_SHARE:
            out.append(Gate("priority", f"Слабость к {HIT_NAMES[h.damage_type]}",
                            f"переживаешь {h.normal:,.0f} ({h.normal / best:.0%} от лучшего типа); "
                            f"критом на сочной карте — {h.juiced:,.0f}"))
    if rec.es_primary:
        out.append(Gate("warn", "Защита держится на энергощите",
                        f"энергощит {rec.energy_shield:,.0f} (жизнь {rec.life:,.0f}): перезаряжается "
                        f"{rec.es_recharge:,.0f}/с, но только после {rec.es_recharge_delay:.1f} с без урона; "
                        "под непрерывными ударами он не восстанавливается"))
    elif rec.half_life_refill_seconds is None:
        out.append(Gate("warn", "Жизнь в бою не восстанавливается",
                        "нет похищения, регенерации и возмещения — здоровье возвращается только флаконами"))
    elif rec.regen == 0:
        out.append(Gate("warn", "Нет регенерации жизни",
                        f"{rec.total:,.0f}/с только пока атакуешь; половина жизни за {rec.half_life_refill_seconds:.1f} с"))
    if rec.leech_capped_per_hit:
        out.append(Gate("warn", "Похищение упёрлось в лимит на удар",
                        "«+% похищения» не поможет; помогут скорость восстановления, больше здоровья, чаще удары"))
    return out


def defence_weights(hits: list) -> dict[str, float]:
    """Weaker damage types count more: weight ~ best / survivable hit, normalised to 1."""
    finite = [h for h in hits if not h.immune] or hits
    best = max(h.normal for h in finite)
    raw = {h.damage_type: 0.0 if h.immune else best / h.normal for h in hits}  # no need to defend an immunity
    total = sum(raw.values())
    return {t: w / total for t, w in raw.items()}


def score(g: Gradient, mode: str, weights: dict[str, float]) -> float:
    w_dps, w_def, w_rec = MODES[mode]
    defence = sum(weights[t] * g.one[HIT_METRIC[t]] for t in DAMAGE_TYPES)
    return w_dps * g.one["dps"] + w_def * defence + w_rec * g.one["recovery"]


@dataclass
class Step:
    mod: str
    score: float
    dps: float  # % change from this step alone
    defence: dict[str, float]  # % change in survivable hit per damage type from this step
    recovery: float
    total_dps: float  # cumulative % vs the original build
    total_defence: dict[str, float]
    total_recovery: float


def _metric_totals(original: dict, current: dict) -> tuple[float, dict, float]:
    pct = lambda new, old: (new - old) / old * 100 if old else 0.0
    return (
        pct(current["CombinedDPS"], original["CombinedDPS"]),
        {t: hit_change(current, original, t) for t in DAMAGE_TYPES},
        pct(recovery_per_second(current), recovery_per_second(original)),
    )


def upgrade_path(engine, profile: MapProfile, mode: str, steps: int, weights: dict[str, float],
                 min_score: float = 0.3, max_repeats: int = 1) -> list[Step]:
    """Greedy: take the best-scoring mod, treat it as applied, re-rank. A stat is used at most max_repeats
    times - the same affix can only sit on a limited number of items."""
    config = profile.config()
    original = engine.what_if(config=config)
    applied: list[str] = []
    used: dict[str, int] = {}
    path = []
    for _ in range(steps):
        _, grads = compute(engine, config=config, base_mods=applied)
        candidates = [g for g in grads if used.get(g.stat.key, 0) < max_repeats]
        if not candidates:
            break
        best = max(candidates, key=lambda g: score(g, mode, weights))
        used[best.stat.key] = used.get(best.stat.key, 0) + 1
        s = score(best, mode, weights)
        if s < min_score:
            break
        line = mod_line(best.stat)
        applied.append(line)
        current = engine.what_if(config=config, mods=applied)
        total_dps, total_def, total_rec = _metric_totals(original, current)
        path.append(Step(
            mod=line, score=s, dps=best.one["dps"],
            defence={t: best.one[HIT_METRIC[t]] for t in DAMAGE_TYPES},
            recovery=best.one["recovery"],
            total_dps=total_dps, total_defence=total_def, total_recovery=total_rec,
        ))
    return path


# Charge types: (name, maximum stat, Configuration checkbox)
CHARGES = [("Power Charges", "PowerChargesMax", "usePowerCharges"),
           ("Frenzy Charges", "FrenzyChargesMax", "useFrenzyCharges"),
           ("Endurance Charges", "EnduranceChargesMax", "useEnduranceCharges")]


def _resource(name, assumed, maximum, off: dict, on: dict, counted: bool, set_in_build: bool) -> dict:
    return {"name": name, "assumed": assumed, "maximum": maximum, "counted": counted, "set_in_build": set_in_build,
            "dps_without": off["CombinedDPS"], "dps_with": on["CombinedDPS"],
            "ehp_without": off.get("TotalEHP", 0), "ehp_with": on.get("TotalEHP", 0)}


def core_damage(engine, profile: MapProfile, grads: list[Gradient]) -> dict:
    """What the damage stands on: resources (Rage, charges) with and without them, and every stat's worth in units
    of the main one."""
    cfg = profile.config()
    with_res = engine.what_if(config=cfg)
    build_cfg = engine.config()
    out = {"resources": [], "unit": None, "exchange": []}
    if with_res.get("MaximumRage", 0) > 0:
        without = engine.what_if(config=cfg | {"multiplierRage": 0})
        out["resources"].append(_resource("Rage", with_res["Rage"], with_res["MaximumRage"], without, with_res,
                                          True, "multiplierRage" in build_cfg))
    for name, max_key, var in CHARGES:
        maximum = with_res.get(max_key, 0)
        if maximum <= 0:
            continue
        off = engine.what_if(config=cfg | {var: False})
        on = engine.what_if(config=cfg | {var: True})
        effect = abs(on["CombinedDPS"] / off["CombinedDPS"] - 1) if off["CombinedDPS"] else 0
        ehp_effect = abs(on.get("TotalEHP", 0) / off["TotalEHP"] - 1) if off.get("TotalEHP") else 0
        if max(effect, ehp_effect) >= 0.005:
            out["resources"].append(_resource(name, maximum if build_cfg.get(var) else 0, maximum, off, on,
                                              bool(build_cfg.get(var)), var in build_cfg))
    rage = next((g for g in grads if g.stat.key == "max_rage"), None)
    if rage and rage.one["dps"] > 0:
        unit_name, per_point = "Maximum Rage", rage.one["dps"] / rage.stat.unit
    else:
        best = max(grads, key=lambda g: g.one["dps"])
        unit_name, per_point = mod_line(best.stat), best.one["dps"]
    out["unit"] = {"name": unit_name, "dps_pct_per_point": per_point}
    if per_point > 0:
        for g in sorted(grads, key=lambda g: -g.one["dps"]):
            if g.one["dps"] >= 0.5:
                out["exchange"].append({"mod": mod_line(g.stat), "dps": g.one["dps"], "points": g.one["dps"] / per_point})
    return out


def build_report(engine, profile: MapProfile, mode: str = "balanced", steps: int = 6, top: int = 10,
                 statdesc_dir=None) -> dict:
    stats = engine.what_if(config=profile.config())
    hits = survivable_hits(engine, profile)
    rec = recovery(engine, profile)
    weights = defence_weights(hits)
    _, grads = compute(engine, config=profile.config())
    ranked = sorted(grads, key=lambda g: -score(g, mode, weights))

    conditions = audit_conditions(engine, profile.config())
    sources = engine.requirement_sources()
    statuses = attrs.status(stats, sources, engine.attribute_node_counts())
    swaps = attrs.node_swaps(engine, profile.config(), statuses)
    deps = attrs.item_dependencies(engine, profile.config(), sources)
    at_risk = {
        s.attr: attrs.supports_at_risk(engine, profile.config(), s.attr)
        for s in statuses if s.margin < 0 and any("Support Gems" in n for n in s.needed_by)
    }
    return {
        "build": {**engine.info(), "mainSkill": engine.main_skill()},
        "profile": asdict(profile),
        "mode": mode,
        "baseline": {
            "dps": stats["CombinedDPS"],
            # a minion build: the damage is the army's (one minion times the active limit), see PobEngine.what_if
            "minions": {"count": stats["MinionCount"], "perMinion": stats.get("Minion.CombinedDPS", 0.0)}
            if stats.get("DpsFromMinions") else None,
            "life": stats["Life"],
            "es": stats.get("EnergyShield", 0.0),
            "hitChance": stats.get("HitChance"),
            "survivableHit": {h.damage_type: asdict(h) for h in hits},
            "recoveryPerSecond": recovery_per_second(stats),
            "recoveryPool": "es" if stats.get("EnergyShield", 0) > stats.get("Life", 0) else "life",
        },
        "gates": [asdict(g) for g in unread_gates(engine) + zero_damage_gates(engine, stats, profile.config())
                  + attribute_gates(statuses, swaps, deps)
                  + gates(stats, hits, rec, profile.mana_sustained)],
        "notModelled": [asdict(g) for g in collect_mechanics(engine, statdesc_dir).gaps if g.likely_impact],
        "conditions": [asdict(c) for c in conditions],
        "damageRange": damage_range(engine, profile.config(), conditions),
        "core": core_damage(engine, profile, grads),
        "attributes": {
            "status": [asdict(s) | {"margin": s.margin} for s in statuses],
            "nodeSwaps": [asdict(s) for s in swaps],
            "itemDependencies": [asdict(d) for d in deps],
            "supportsAtRisk": {a: [asdict(s) for s in lst] for a, lst in at_risk.items()},
        },
        "defenceWeights": weights,
        "ranking": [
            {"mod": mod_line(g.stat), "score": score(g, mode, weights), "dps": g.one["dps"],
             "physHit": g.one["phys_hit"], "chaosHit": g.one["chaos_hit"], "recovery": g.one["recovery"]}
            for g in ranked[:top] if score(g, mode, weights) > 0
        ],
        "path": [asdict(s) for s in upgrade_path(engine, profile, mode, steps, weights)],
    }
