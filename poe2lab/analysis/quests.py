"""The campaign's rewards that change the character (PoB's "Quest Rewards" configuration, data.questRewards): the
fixed ones (resistances, Spirit, life) and the choices (Tribal Medicine: Kaom's or Rakiata's Lesson, the
ancestors' tests, the Seven Pillars...). Each option of a choice is priced by PoB on the build - in its place, not on
top of what the build has chosen - and scored for the build's goal, so the player sees which to take."""
from .gradients import metric_changes
from .report import defence_weights
from .threats import survivable_hits
from .tree import _value

# a choice PoB does not see in its numbers is not "no worth": what each kind of option is for, in words
# (the experience pillar names every other stat reduced: it goes first)
BLIND = [("Experience", "experience"), ("Charm", "charms"), ("Flask", "flasks"), ("Movement Speed", "speed"),
         ("Presence", "presence"), ("Cooldown", "cooldown"), ("Mana Regeneration", "mana"),
         ("Ailment Threshold", "ailments"), ("Stun Threshold", "stun"), ("Attributes", "attributes"),
         ("to Strength", "attributes"), ("to Dexterity", "attributes"), ("to Intelligence", "attributes")]
TIE = 0.5  # a score this close to the best is as good: no single best then


def option_lines(option: str) -> list[str]:
    return [line.strip() for line in option.split("\n") if line.strip()]


def _blind(option: str) -> str | None:
    return next((key for word, key in BLIND if word.lower() in option.lower()), None)


def rewards(engine, profile, mode: str = "balanced") -> dict:
    """Every reward with what it gives the build (PoB) and, for a choice, the best option for the goal."""
    config = profile.config()
    rows = engine.quest_rewards()
    weights = defence_weights(survivable_hits(engine, profile))
    choices, fixed = [], []
    for r in rows:
        if r.get("options"):
            base = engine.what_if(config=config | {r["var"]: "None"})
            options = []
            for opt in r["options"]:
                changes = metric_changes(engine.what_if(config=config | {r["var"]: opt}), base)
                options.append({"value": opt, "lines": option_lines(opt), "changes": changes,
                                "score": _value(changes, mode, weights), "blind": _blind(opt)})
            top = max(o["score"] for o in options)
            best = [o for o in options if o["score"] >= top - TIE] if top > TIE else []
            for o in options:
                o["best"] = len(best) == 1 and o is best[0]
            choices.append(r | {"options": options, "chosen": r["value"] if r["value"] != "None" else None})
        else:
            on = engine.what_if(config=config | {r["var"]: True})
            off = engine.what_if(config=config | {r["var"]: False})
            fixed.append(r | {"lines": option_lines(r["stat"]), "changes": metric_changes(on, off),
                              "taken": bool(r["value"])})
    return {"choices": choices, "fixed": fixed, "mode": mode,
            "unchosen": [c["var"] for c in choices if c["chosen"] is None]}


def valid(rows: list[dict], var: str, value) -> bool:
    """A value the reward can have: one of its options or "None", or on/off for a fixed one."""
    r = next((x for x in rows if x["var"] == var), None)
    if r is None:
        return False
    if r.get("options"):
        return value == "None" or value in r["options"]
    return isinstance(value, bool)
