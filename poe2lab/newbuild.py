"""A build made from nothing: a class, its ascendancy and a stage's level, as an empty PoB build.

This is the first step of the build constructor (PLAN.md, "Конструктор билда с нуля"). The build has no passives,
gems or items yet. The next steps add them with the editors poe2lab already has. It is written the way a .build
file's skeleton is (poe2lab.buildplanner.skeleton), so PoB reads it like a build of its own."""
from . import buildplanner

# a stage of the game -> the character level the build is made for
STAGES = {"campaign": 60, "maps": 80, "endgame": 92}


def classes(engine) -> list[dict]:
    """The classes of PoB's tree with their ascendancies (the planner's internal id: Monk2 = Invoker) and the
    attributes each class starts with."""
    rows = engine._json("""
local out = _poe2lab_array({})
for id, c in pairs(build.spec.tree.classes) do
  local asc = _poe2lab_array({})
  for aid, a in pairs(c.classes or {}) do
    if aid > 0 and a.internalId then asc[#asc + 1] = { order = aid, name = a.name, id = a.internalId } end
  end
  out[#out + 1] = { order = id, name = c.name, str = c.base_str or 0, dex = c.base_dex or 0, int = c.base_int or 0,
                    ascendancies = asc }
end
return _poe2lab_json(out)""")
    for c in rows:
        c["ascendancies"].sort(key=lambda a: a["order"])
    return sorted(rows, key=lambda c: c["order"])


def level_of(stage: str, level: int | None = None) -> int:
    """The character level for a stage, or the player's own (1-100)."""
    if level is not None:
        return max(1, min(int(level), 100))
    if stage not in STAGES:
        raise ValueError(f"неизвестная стадия {stage!r}")
    return STAGES[stage]


def empty_build(engine, ascendancy: str, level: int) -> str:
    """The PoB XML of a build of this ascendancy (its internal id) at this level: no passives, gems or items."""
    data = {"ascendancy": ascendancy, "passives": [], "skills": [], "inventory_slots": []}
    resolved = buildplanner._resolve(engine, data)
    if not resolved.get("class"):
        raise ValueError(f"нет такого возвышения: {ascendancy}")
    xml, _, _ = buildplanner.skeleton(data, resolved, level=level)
    return xml
