---
name: poe2-build
description: Analyse a Path of Exile 2 build with the local PoB engine in this repo - what to fix, which stats/mods are worth most, what can kill the character on maps, per-slot crafting targets, rune/soul core choices with prices, and exact comparison of a candidate item (e.g. "is this talisman better", "разбери мой билд", "что докрафтить", "стоит ли брать эту руну"). Use whenever the user asks about their PoE2 character, gear, passives or upgrades in this project.
---

# PoE2 build analysis (poe2lab)

All numbers come from Path of Building (headless, `pob2/` submodule) driven by the `poe2lab` package. Run everything
from the repo root. On Windows set `PYTHONIOENCODING=utf-8` so Russian output prints. Answer the user in Russian.

## 1. Get the build

- The user exports a PoB code: PoB-PoE2 -> Import/Export Build -> (Authorize with Path of Exile, pick the character,
  import) -> Generate -> Copy. Save it as `builds/<name>.txt` (the file holds only the code).
- The code contains no account data, but it does reveal the build; mention this before committing it to git.

## 2. Pin down the main skill — ask, do not guess

`python -m poe2lab inspect builds/<name>.txt` lists socket groups (index, skills) and compares our numbers with the
stats stored in the code. Ask which skill carries the damage and pass it as `--group N [--skill M]` to every command
(a group can hold several active skills; `--skill` picks one). Wrong group = every damage number is meaningless.
If the user can, have them confirm Life/ES/armour/resistances against the in-game character sheet.

## 3. Pick the command for the question

| Question | Command |
|---|---|
| "Разбери билд", what is broken, where to invest | `python -m poe2lab report builds/X.txt --group N --mode balanced` (`damage` / `defence` goals) |
| What kills me on maps, how fast I heal | `python -m poe2lab threats builds/X.txt --group N --map-damage 50 --map-crit 50` |
| What to craft / look for in each slot, runes | `python -m poe2lab slots builds/X.txt --group N [--league "<league>"]` |
| Is this item better (item text from game Ctrl+C or edited PoB text) | `python -m poe2lab compare builds/X.txt --group N --slot "Weapon 1" --item new.txt [--breakeven "<mod line>"]`; `--dump cur.txt` saves the worn item to edit |
| Which passives carry the build | `python -m poe2lab nodes builds/X.txt --group N` |
| Raw stat values | `python -m poe2lab gradients builds/X.txt --group N` |
| Everything as JSON (for your own reasoning) | `python -m poe2lab dossier builds/X.txt --group N --out <scratchpad>/d.json` |

Slot names: `Weapon 1`, `Helmet`, `Body Armour`, `Gloves`, `Boots`, `Amulet`, `Ring 1`, `Ring 2`, `Belt`.

## 4. Traps found on real builds — always check and tell the user

- **Resources the PoB sidebar ignores.** If the Configuration field is empty PoB computes with 0 Rage. The report's
  "ЯДРО УРОНА" shows the build with maximum Rage (a Titan went x2.3). Ask the user their typical combat Rage (`--rage`).
- **Attribute requirements.** An unmet requirement disables an item/gem in game while PoB keeps counting it. For
  support gems the requirement is per colour count; the game switches one support off and PoB cannot say which —
  the report lists the cost of each candidate. The cheapest fix is often re-choosing one attribute passive (+5).
- **Conditional effects.** Effects behind an unticked Configuration box count as zero (Momentum looked worthless).
  The report's "УСЛОВИЯ" section lists relevant boxes and their value; ask which ones hold in real play.
- **Load-bearing and utility affixes.** Never advise removing affixes the slot plan marks НЕСУЩИЙ (spirit for
  reservations, attribute requirements, resistance caps, mana) or утилити (movement speed, rarity…), even if PoB
  scores them at zero.
- **Mana.** The report warns when the main skill spends more mana per second than regen + leech; gem level mods raise
  mana cost too.
- **Monster hits.** PoB has no real PoE2 monster skill data. Threat numbers are the largest monster base hit survived
  (normal / crit / juiced map); present them as "what you survive", not "what kills you". Map values are assumptions.
- **Crafting path** is a target set of affixes from mods that can roll on that base at that item level (with
  essence/desecration sources), not a procedure: PoE2 client data has no real spawn weights, so do not promise odds
  or crafting cost.
- **Prices** (poe.ninja, cached 1 h) are often thin markets ("мало сделок"); treat them as rough.

## 5. How to answer

Lead with the one or two changes that matter most, with numbers (e.g. "Soul Core of Tacati в ботинки: хаос-удар
+43%, ~36 ex"). Separate "сломано в игре" from "можно улучшить". State assumptions you used (main skill, Rage,
enemy level 79 / map juice, league). Open questions for the user live in `QUESTIONS.md`; add new ones there.
