"""The page's own text helpers (static/i18n.js), run in Node: game texts PoB splits over several lines, and granted
skills in the game's wording."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "poe2lab" / "web" / "static"
NODE = shutil.which("node")


def run_js(files: list[str], code: str):
    """Evaluate `code` after the page scripts `files`, in one Node context; the result as JSON."""
    script = ("const vm = require('vm'); const fs = require('fs'); const ctx = vm.createContext({ console });"
              + "".join(f"vm.runInContext(fs.readFileSync({json.dumps(str(STATIC / f))}, 'utf8'), ctx);" for f in files)
              + f"process.stdout.write(JSON.stringify(vm.runInContext({json.dumps(code)}, ctx)));")
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="no Node.js")
def test_multi_line_game_texts_and_granted_skills():
    shown = run_js(["i18n.js"], """
      GAME = { stats: {
        'can tattoo runes onto your body, gaining additional rune-only sockets: • # helmet socket • # body armour sockets':
          'Позволяет наносить руны: • # гнездо для шлема • # гнезда для нательного доспеха',
        '#% increased damage': '#% увеличение урона' }, names: { 'Meditate': 'Медитация' } };
      bulletless = null; LANG = 'ru';
      trLines(['10% increased Damage', 'Can tattoo Runes onto your body, gaining', 'additional Rune-only sockets:',
               '1 Helmet socket', '2 Body Armour sockets', 'Grants Skill: Meditate', 'Grants Skill: Level 5 Meditate',
               'Some line no template knows'])
    """)
    assert [text for _, text in shown] == [
        "10% увеличение урона", "Позволяет наносить руны:", "• 1 гнездо для шлема", "• 2 гнезда для нательного доспеха",
        "Дарует умение: Медитация", "Дарует умение: Медитация 5 уровня", "Some line no template knows"]
    # the joined lines keep the whole English text for the hover
    assert shown[1][0] == shown[2][0] == ("Can tattoo Runes onto your body, gaining additional Rune-only sockets: "
                                          "1 Helmet socket 2 Body Armour sockets")


@pytest.mark.skipif(not NODE, reason="no Node.js")
def test_english_lines_pass_through():
    shown = run_js(["i18n.js"], "LANG = 'en'; trLines(['Grants Skill: Meditate', 'a', 'b'])")
    assert shown == [["Grants Skill: Meditate"] * 2, ["a", "a"], ["b", "b"]]


# ---------- the tree art's BC7 decoder (static/treeart.js) against blocks written bit by bit here ----------
BLOCK_WRITER = """
  const block = () => { const b = new Uint8Array(16); let pos = 0;
    return { b, put(v, n) { for (let i = 0; i < n; i++, pos++) if ((v >> i) & 1) b[pos >> 3] |= 1 << (pos & 7); } }; };
"""
W4 = [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]
W3 = [0, 9, 18, 27, 37, 46, 55, 64]


def lerp(a, b, w):
    return ((64 - w) * a + w * b + 32) >> 6


@pytest.mark.skipif(not NODE, reason="no Node.js")
def test_bc7_one_subset_with_alpha():
    """Mode 6: 7-bit RGBA endpoints plus a p-bit each, 4-bit indices (the first pixel's one bit shorter)."""
    px = run_js(["treeart.js"], BLOCK_WRITER + """
      const w = block();
      w.put(1 << 6, 7);
      [[0, 127], [64, 64], [10, 20], [127, 127]].forEach(([a, b]) => { w.put(a, 7); w.put(b, 7); });
      w.put(0, 1); w.put(1, 1);
      for (let i = 0; i < 16; i++) w.put(i, i === 0 ? 3 : 4);
      const out = new Uint8Array(64); bc7Block(w.b, 0, out); Array.from(out)
    """)
    ends = [(0, 255), (128, 129), (20, 41), (254, 255)]  # (value << 1 | p-bit)
    assert px == [lerp(a, b, W4[i]) for i in range(16) for a, b in ends]


@pytest.mark.skipif(not NODE, reason="no Node.js")
def test_bc7_two_subsets_by_partition():
    """Mode 1: partition 13 puts the lower half in the second subset (its anchor is pixel 15); 6-bit colours with
    one p-bit shared per subset; 3-bit indices."""
    px = run_js(["treeart.js"], BLOCK_WRITER + """
      const w = block();
      w.put(2, 2); w.put(13, 6);
      [[0, 63, 10, 40], [5, 6, 7, 8], [63, 0, 33, 1]].forEach((ch) => ch.forEach((v) => w.put(v, 6)));
      w.put(1, 1); w.put(0, 1);
      for (let i = 0; i < 16; i++) w.put(i % 8 === 7 && i === 15 ? 3 : i % 8, i === 0 || i === 15 ? 2 : 3);
      const out = new Uint8Array(64); bc7Block(w.b, 0, out); Array.from(out)
    """)

    def expand(v6, p):
        v = (v6 << 1) | p
        return (v << 1) | (v >> 6)
    subsets = [[(expand(a, 1), expand(b, 1)) for a, b in ((0, 63), (5, 6), (63, 0))],
               [(expand(a, 0), expand(b, 0)) for a, b in ((10, 40), (7, 8), (33, 1))]]
    want = []
    for i in range(16):
        index = 3 if i == 15 else i % 8
        want += [lerp(a, b, W3[index]) for a, b in subsets[i // 8]] + [255]
    assert px == want


@pytest.mark.skipif(not NODE, reason="no Node.js")
def test_templates_with_their_own_order_of_numbers():
    shown = run_js(["i18n.js"], """
      GAME = { stats: { '#% chance to defend with #% of armour': '#{0}% шанс на защиту с удвоенной броней',
                        '# to # fire damage for # seconds': 'На #{2} с: от #{0} до #{1} урона от огня' }, names: {} };
      LANG = 'ru';
      [trMod('10% chance to Defend with 200% of Armour'), trMod('3 to 7 Fire Damage for 4 seconds')]
    """)
    assert shown == ["10% шанс на защиту с удвоенной броней", "На 4 с: от 3 до 7 урона от огня"]
