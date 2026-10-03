// The description editor's search: by name and by tags, in the order the app's constructor uses (poe2lab/author.py):
// the whole name, its start, a word's start, anywhere in the name, then the things found by their tags.
import { THINGS, type GameThing } from "~~/mock/game";

const norm = (s: string) => s.toLowerCase().replace(/ё/g, "е").trim();
const starts = (w: string, text: string) => new RegExp(`(^|[\\s\\-'(«])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(text);

export function lookup(query: string, kinds: GameThing["kind"][] | null = null, limit = 20): GameThing[] {
  const words = norm(query).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const phrase = words.join(" ");
  const scored: [number, GameThing][] = [];
  for (const g of THINGS) {
    if (kinds && !kinds.includes(g.kind)) continue;
    const name = norm(g.card.name);
    let rank: number | null = null;
    if (words.every((w) => name.includes(w))) {
      rank = name === phrase ? 0 : name.startsWith(phrase) ? 1 : words.every((w) => starts(w, name)) ? 2 : 3;
    } else {
      const tags = g.tags.map(norm);
      const strong = words.map((w) => tags.some((t) => t.startsWith(w)));
      const weak = words.map((w) => tags.some((t) => starts(w, t)));
      const named = words.map((w) => starts(w, name));
      if (weak.some(Boolean) && words.every((_, i) => weak[i] || named[i])) rank = words.every((_, i) => strong[i] || named[i]) ? 4 : 5;
    }
    if (rank !== null) scored.push([rank, g]);
  }
  return scored.sort((a, b) => a[0] - b[0] || a[1].card.name.length - b[1].card.name.length).slice(0, limit).map((x) => x[1]);
}

// a tag lit when a word of the query begins it
export const tagHit = (tag: string, query: string) => norm(query).split(/\s+/).filter(Boolean).some((w) => norm(tag).split(/\s+/).some((x) => x.startsWith(w)));
export const cardsOf = () => Object.fromEntries(THINGS.map((g) => [g.key, g.card]));
