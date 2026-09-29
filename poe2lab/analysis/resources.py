"""Resources a build builds up in a fight - Rage and the three charges: how much of each it really has, from what
makes them (the lines of its passives and gear, its gems' stats) against how fast they go.

PoB takes the number it is given (the Configuration tab: Rage, "do you use charges", how many) and puts it on every
hit. Given "maximum", a node that only makes Rage faster is worth nothing to it, and a build that barely keeps
Rage up is priced as if it were full. Here the fight is played out step by step - the gains of the build's sources
at the rate its main skill hits, the losses PoB counts (inherent Rage loss after a delay, charges running out) - and
the average during combat is what PoB is given. A node is then priced at the level it brings: faster Rage is worth
what the Rage it adds gives. What skills spend is not taken off: players alternate builders and spenders, and PoB
prices a spender's bonus as there - the build-up at the start of each fight and the loss between packs are what a
faster source shortens.

Events the game does not count for us (being hit, kills, heavy stuns, flasks) happen at the rates of FIGHT, a map's
packs or a boss - an assumption, stated where it is shown."""
import re
from dataclasses import dataclass, field

CHARGES = ("frenzy", "power", "endurance")
RAGE_BASE_MAX = 30  # the game's base maximum Rage (PoB's tooltip), for a build that has no Rage yet
DT = 0.1  # seconds per step of the fight

# the fights played out: a map's packs (fighting, then a walk to the next) and a boss (one long fight)
MAP_PACKS, MAP_FIGHT, MAP_GAP = 4, 6.0, 3.0
BOSS_FIGHT = 40.0
# events per second the game does not tell us, on maps and against a boss
FIGHT = {
    "map": {"kill": 1.0, "hit_taken": 1.0, "flask": 1 / 8, "warcry": 1 / 8, "heavy_stun": 0.5, "heavy_stun_unique": 0.0,
            "armour_break": 0.5, "stun": 1.0, "rare": 0.25},
    "boss": {"kill": 0.05, "hit_taken": 0.5, "flask": 1 / 8, "warcry": 1 / 8, "heavy_stun": 0.0, "heavy_stun_unique": 0.1,
             "armour_break": 0.3, "stun": 0.2, "rare": 0.25},
}


@dataclass
class Sources:
    """What makes and keeps one resource: gains (event, amount, chance), regeneration, and what changes the pool."""
    gains: list[tuple[str, float, float]] = field(default_factory=list)  # (event, amount, chance 0..1)
    regen: float = 0.0  # per second
    regen_pct: float = 0.0  # % of the maximum per second
    to_max: float = 0.0  # chance per gain to fill up instead
    extra: float = 0.0  # chance per gain to gain one more
    max_add: float = 0.0
    max_more: float = 0.0  # % more maximum
    duration_inc: float = 0.0  # % increased duration (charges)
    loss_slower: float = 0.0  # % slower inherent loss (Rage)
    delay_add: float = 0.0  # seconds later the loss starts
    delay_faster: float = 0.0  # % faster start of the loss
    no_loss: bool = False

    _NUMBERS = ("regen", "regen_pct", "to_max", "extra", "max_add", "max_more", "duration_inc", "loss_slower",
                "delay_add", "delay_faster")

    def merge(self, other: "Sources", sign: int = 1) -> "Sources":
        """These sources with another's added (sign 1) or taken away (sign -1)."""
        out = Sources(gains=list(self.gains), no_loss=self.no_loss or (sign > 0 and other.no_loss))
        if sign > 0:
            out.gains += other.gains
        else:
            for g in other.gains:
                if g in out.gains:
                    out.gains.remove(g)
            out.no_loss = self.no_loss and not other.no_loss
        for name in self._NUMBERS:
            setattr(out, name, max(0.0, getattr(self, name) + sign * getattr(other, name)))
        return out

    @property
    def any(self) -> bool:
        """Does anything make this resource?"""
        return bool(self.gains or self.regen or self.regen_pct)


_N = r"(\d+(?:\.\d+)?)"
_CH = r"(frenzy|power|endurance)"


def _gain(res, event, amount=1.0, chance=1.0):
    return res, Sources(gains=[(event, float(amount), float(chance))])


# a line of a passive or an item -> (resource, what it adds); `c` says what the build is (melee, axe, shapeshift)
_LINE_RULES = [
    (rf"gain {_N} rage on melee axe hit", lambda m, c: _gain("rage", "melee_hit", m[1]) if c["axe"] else None),
    (rf"gain {_N} rage on melee hit", lambda m, c: _gain("rage", "melee_hit", m[1])),
    (rf"gain {_N} rage on (?:attack )?hit", lambda m, c: _gain("rage", "hit", m[1])),
    (rf"gain {_N} rage when hit by an enemy", lambda m, c: _gain("rage", "hit_taken", m[1])),
    (rf"gain {_N} rage when you use a life flask", lambda m, c: _gain("rage", "flask", m[1])),
    (rf"gain {_N} rage when your hit ignites", lambda m, c: _gain("rage", "ignite", m[1])),
    (rf"gain {_N} rage when you kill", lambda m, c: _gain("rage", "kill", m[1])),
    (rf"gain {_N} rage when you use a warcry", lambda m, c: _gain("rage", "warcry", m[1])),
    (rf"^regenerate {_N}% of your maximum rage per second", lambda m, c: ("rage", Sources(regen_pct=float(m[1])))),
    (rf"^regenerate {_N} rage per second$", lambda m, c: ("rage", Sources(regen=float(m[1])))),
    (rf"{_N}% chance that if you would gain rage on hit, you instead gain up to your maximum",
     lambda m, c: ("rage", Sources(to_max=float(m[1]) / 100))),
    (rf"inherent loss of rage is {_N}% slower", lambda m, c: ("rage", Sources(loss_slower=float(m[1])))),
    (rf"inherent rage loss starts {_N} seconds? later", lambda m, c: ("rage", Sources(delay_add=float(m[1])))),
    (rf"{_N}% faster start of inherent rage loss", lambda m, c: ("rage", Sources(delay_faster=float(m[1])))),
    (r"no inherent loss of rage", lambda m, c: ("rage", Sources(no_loss=True))),
    (rf"^\+{_N} to maximum rage$", lambda m, c: ("rage", Sources(max_add=float(m[1])))),
    (rf"^\+{_N} to maximum rage while shapeshifted",
     lambda m, c: ("rage", Sources(max_add=float(m[1]))) if c["shapeshift"] else None),
    (rf"^\+{_N} to maximum rage while wielding an axe",
     lambda m, c: ("rage", Sources(max_add=float(m[1]))) if c["axe"] else None),
    (rf"{_N}% more maximum rage", lambda m, c: ("rage", Sources(max_more=float(m[1])))),
    (rf"{_N}% chance when you gain an? {_CH} charge to gain an additional",
     lambda m, c: (m[2], Sources(extra=float(m[1]) / 100))),
    (rf"{_N}% chance that if you would gain {_CH} charges, you instead gain up to",
     lambda m, c: (m[2], Sources(to_max=float(m[1]) / 100))),
    (rf"{_N}% increased {_CH} charge duration", lambda m, c: (m[2], Sources(duration_inc=float(m[1])))),
    (rf"^\+{_N} to maximum {_CH} charges", lambda m, c: (m[2], Sources(max_add=float(m[1])))),
    (rf"gain an? {_CH} charge when you heavy stun a rare or unique", lambda m, c: _gain(m[1], "heavy_stun_unique")),
    (rf"gain an? {_CH} charge when you consume", lambda m, c: _gain(m[1], "rare")),
    (rf"{_N}% chance to gain an? {_CH} charge on kill", lambda m, c: _gain(m[2], "kill", 1, float(m[1]) / 100)),
    (rf"{_N}% chance to gain an? {_CH} charge on critical hit", lambda m, c: _gain(m[2], "crit", 1, float(m[1]) / 100)),
    (rf"{_N}% chance to gain an? {_CH} charge on hit", lambda m, c: _gain(m[2], "hit", 1, float(m[1]) / 100)),
    (rf"gain an? {_CH} charge on kill", lambda m, c: _gain(m[1], "kill")),
    (rf"gain an? {_CH} charge on critical hit", lambda m, c: _gain(m[1], "crit")),
]
_LINE_RULES = [(re.compile(p), fn) for p, fn in _LINE_RULES]
_ALL_DURATION = re.compile(rf"{_N}% increased endurance, frenzy and power charge duration")

# a gem's stat (PoB's gem data, at the gem's level) -> (resource, what it adds)
_GEM_RULES = {
    "gain_x_rage_on_melee_hit": lambda v: _gain("rage", "melee_hit", v),
    "gain_x_rage_on_attack_hit": lambda v: _gain("rage", "hit", v),
    "gain_x%_of_maximum_rage_on_melee_hit": lambda v: _gain("rage", "melee_hit_pct", v),
    "gain_x_endurance_charges_on_heavy_stunning_unique_enemy": lambda v: _gain("endurance", "heavy_stun_unique", v),
    "chance_to_gain_endurance_charge_on_heavy_stunning_non_unique_enemy_%":
        lambda v: _gain("endurance", "heavy_stun", 1, v / 100),
    "chance_to_gain_endurance_charge_on_armour_break_%": lambda v: _gain("endurance", "armour_break", 1, v / 100),
    "chance_to_gain_endurance_charge_on_perfect_timing_hit_%": lambda v: _gain("endurance", "rare", 1, v / 100),
    "igneous_shield_gain_endurance_charge_on_block": lambda v: _gain("endurance", "block"),
    "wing_blast_chance_to_gain_power_charge_on_stun_%": lambda v: _gain("power", "stun", 1, v / 100),
    "chance_to_gain_1_more_frenzy_charge_%": lambda v: ("frenzy", Sources(extra=v / 100)),
}


def _add(out: dict, res: str, s: Sources):
    out[res] = out.get(res, Sources()).merge(s)


def read_lines(lines, ctx: dict) -> dict[str, Sources]:
    """The resources lines of passives or gear make or change."""
    out: dict[str, Sources] = {}
    for line in lines:
        low = line.lower().strip()
        if m := _ALL_DURATION.search(low):
            for ch in CHARGES:
                _add(out, ch, Sources(duration_inc=float(m[1])))
            continue
        for pattern, rule in _LINE_RULES:
            if (m := pattern.search(low)) and (hit := rule(m, ctx)):
                _add(out, *hit)
                break
    return out


def read_gems(gems) -> dict[str, Sources]:
    """The resources the build's gems make (their stats' values at the gems' levels)."""
    out: dict[str, Sources] = {}
    for gem in gems:
        stats = gem["stats"] if isinstance(gem["stats"], dict) else {}  # an empty Lua table comes as a list
        for stat, value in stats.items():
            rule = _GEM_RULES.get(stat)
            if rule and isinstance(value, (int, float)) and value:
                _add(out, *rule(float(value)))
    return out


def fight(src: Sources, rates: dict, maximum: float, loss: float, delay: float, duration: float, scenario: str) -> dict:
    """Plays the fight out: the resource's average while fighting and when it first gets full (seconds of
    fighting). Gains come at their events' rates (fractional, as an average), the pool is capped; Rage is lost
    (`loss` per second) once nothing added any for `delay` seconds; charges all run out `duration` seconds after
    the last one came."""
    gain_rate = fill_rate = event_rate = 0.0
    for event, amount, chance in src.gains:
        per_event = amount * maximum / 100 if event == "melee_hit_pct" else amount
        rate = rates.get("melee_hit" if event == "melee_hit_pct" else event, 0.0) * chance
        gain_rate += per_event * rate * (1 + src.extra)
        fill_rate += rate * src.to_max
        event_rate += rate
    regen = src.regen + src.regen_pct * maximum / 100
    # charges come one event at a time (at the events' average spacing) and can run out between them; Rage comes
    # in many small gains, taken as a steady flow
    per_event = gain_rate / event_rate if event_rate else 0.0
    to_max = fill_rate / event_rate if event_rate else 0.0
    level, since_gain, total, seconds, full_at, pending = 0.0, 1e9, 0.0, 0.0, None, 0.0
    phases = [(MAP_FIGHT, True), (MAP_GAP, False)] * MAP_PACKS if scenario == "map" else [(BOSS_FIGHT, True)]
    for length, fighting in phases:
        for _ in range(int(round(length / DT))):
            if duration > 0:
                gained = 0.0
                pending += event_rate * DT if fighting else 0.0
                while pending >= 1:
                    pending -= 1
                    gained += per_event + to_max * (maximum - level - gained)
            else:
                gained = (gain_rate + fill_rate * (maximum - level)) * DT if fighting else 0.0
                gained += regen * DT
            if gained > 0:
                level = min(maximum, level + gained)
                since_gain = 0.0
            else:
                since_gain += DT
            if duration > 0:  # charges: all gone when none came for their duration
                if since_gain >= duration:
                    level = 0.0
            elif since_gain >= delay:  # Rage: lost at its rate once the delay is over
                level = max(0.0, level - loss * DT)
            if fighting:
                total += level * DT
                seconds += DT
                if full_at is None and level >= maximum - 1e-6:
                    full_at = round(seconds, 1)
    return {"level": total / seconds if seconds else 0.0, "max": maximum, "fullAfter": full_at}


@dataclass
class ResourceModel:
    """The build's resources as they are, and as nodes taken or dropped would make them (`levels(add_lines=...,
    remove=...)`), turned into PoB's configuration (`config(levels)`)."""
    base: dict  # resource -> Sources of the build as it is
    node_sources: dict  # allocated node id -> {resource: Sources}
    rates: dict
    out: dict  # PoB's numbers the fight starts from: maxima, durations, Rage loss
    scenario: str
    ctx: dict
    user_rage: bool  # the player (or the build's author) said how much Rage there is: that stands

    @classmethod
    def of(cls, engine, profile, output: dict) -> "ResourceModel":
        main = next((g for g in engine.skill_groups() if g.get("main")), None)
        types = {t for a in (main or {}).get("actives", []) for t in a.get("types", [])}
        gear = engine.equipped_item_details()
        weapons = {i["type"] for i in gear if i["slot"] in ("Weapon 1", "Weapon 2")}
        ctx = {"melee": "Melee" in types, "axe": any("Axe" in w for w in weapons), "shapeshift": "Shapeshift" in types}
        per_node = {i: read_lines(lines, ctx) for i, lines in engine.node_lines().items()}
        items = [e["line"] for it in gear if "Swap" not in it["slot"]
                 for key in ("implicit", "explicit", "enchant") for e in it.get(key, []) if isinstance(e, dict)]
        base: dict[str, Sources] = {}
        for part in [*per_node.values(), read_lines(items, ctx), read_gems(engine.gem_stat_values())]:
            for res, s in part.items():
                _add(base, res, s)
        hits = (output.get("Speed") or 0) * (output.get("HitChance") or 100) / 100
        scenario = "map" if profile.boss == "None" else "boss"
        rates = dict(FIGHT[scenario]) | {
            "hit": hits, "melee_hit": hits if ctx["melee"] else 0.0,
            "crit": hits * (output.get("CritChance") or 0) / 100,
            "ignite": hits * (output.get("IgniteChancePerHit") or 0) / 100,
            "block": FIGHT[scenario]["hit_taken"] * (output.get("BlockChance") or 0) / 100}
        # a Rage the player (or the build's author) put down stands; unset (none, 0) or "maximum" is modelled
        return cls(base=base, node_sources=per_node, rates=rates, out=output, scenario=scenario, ctx=ctx,
                   user_rage=bool(profile.rage) and profile.rage < 9999)

    def _sources(self, add_lines=(), remove=()) -> dict[str, Sources]:
        out = dict(self.base)
        for node in remove:
            for res, s in self.node_sources.get(node, {}).items():
                out[res] = out.get(res, Sources()).merge(s, sign=-1)
        for res, s in read_lines(add_lines, self.ctx).items():
            _add(out, res, s)
        return out

    def levels(self, add_lines=(), remove=()) -> dict[str, dict]:
        """resource -> {level, max, fullAfter}: the average while fighting. Rage is modelled when the build has a
        source of it and nobody set it; a charge when the build has a source of it (else its own answer stands)."""
        src = self._sources(add_lines, remove)
        out = {}
        rage = src.get("rage")
        if rage and rage.any and not self.user_rage:
            base = self.base.get("rage", Sources())
            maximum = (self.out.get("MaximumRage") or RAGE_BASE_MAX) + rage.max_add - base.max_add
            maximum *= (1 + rage.max_more / 100) / (1 + base.max_more / 100)
            loss = 0.0 if rage.no_loss else (self.out.get("InherentRageLoss") or 10) \
                * (1 - rage.loss_slower / 100) / max(0.01, 1 - base.loss_slower / 100)
            delay = ((self.out.get("InherentRageLossDelay") or 2) + rage.delay_add - base.delay_add) \
                / max(0.01, 1 + (rage.delay_faster - base.delay_faster) / 100)
            out["rage"] = fight(rage, self.rates, max(1.0, maximum), loss, max(0.0, delay), 0.0, self.scenario)
        for ch in CHARGES:
            s = src.get(ch)
            if not (s and s.any):
                continue
            base = self.base.get(ch, Sources())
            key = ch.capitalize()
            maximum = (self.out.get(f"{key}ChargesMax") or 0) + s.max_add - base.max_add
            if maximum <= 0:
                continue
            duration = (self.out.get(f"{key}ChargesDuration") or 15) * (1 + (s.duration_inc - base.duration_inc) / 100)
            out[ch] = fight(s, self.rates, maximum, 0.0, 0.0, duration, self.scenario)
        return out

    @staticmethod
    def config(levels: dict) -> dict:
        """PoB's configuration for these levels: Rage in combat, charges used and how many."""
        cfg = {}
        if "rage" in levels:
            cfg["multiplierRage"] = int(round(levels["rage"]["level"]))
        for ch in CHARGES:
            if ch in levels:
                n = levels[ch]["level"]
                key = ch.capitalize()
                cfg[f"use{key}Charges"] = n >= 0.5
                cfg[f"override{key}Charges"] = int(round(n))
        return cfg

    def touches(self, lines) -> bool:
        """Do these lines make or change a resource (a node with them is priced at the level it brings)?"""
        return bool(read_lines(lines, self.ctx))
