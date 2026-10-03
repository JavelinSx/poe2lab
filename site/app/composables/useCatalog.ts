// The catalog's state lives in the page's address (a selection can be shared by its link): the class and its
// ascendancies, damage types, weapons, tags, the patch, the search words, the sort, the view and how many are shown.
// Until the API answers /api/builds, the mock builds are filtered here the same way.
import { BUILDS, CLASSES, CURRENT_PATCH, DMG, TAGS, WEAPONS, type BuildCard } from "~~/mock/builds";

export const PAGE = 24;
export const SORTS = [{ key: "rating", name: "По рейтингу" }, { key: "popular", name: "Популярные" },
  { key: "new", name: "Новые" }, { key: "dps", name: "По урону" }] as const;

const list = (v: unknown) => (Array.isArray(v) ? v : v ? [v] : []).map(String).filter(Boolean);
const norm = (s: string) => s.toLowerCase().replace(/ё/g, "е");

// a word of the search that is a tag, a damage type, a weapon or a class: it becomes a plate in the field
export function knownWord(w: string): { kind: "tag" | "dmg" | "weapon" | "cls"; key: string; name: string } | null {
  const n = norm(w);
  const tag = TAGS.find((t) => norm(t.name) === n);
  if (tag) return { kind: "tag", key: tag.name, name: tag.name };
  const dmg = DMG.find((d) => norm(d.name) === n);
  if (dmg) return { kind: "dmg", key: dmg.key, name: dmg.name };
  const weapon = WEAPONS.find((x) => norm(x) === n || norm(x).split(" ").pop() === n);
  if (weapon) return { kind: "weapon", key: weapon, name: weapon };
  const cls = CLASSES.find((c) => norm(c.name) === n);
  if (cls) return { kind: "cls", key: cls.key, name: cls.name };
  return null;
}

export function useCatalog() {
  const route = useRoute();
  const router = useRouter();
  const q = computed(() => route.query);
  const state = computed(() => ({
    cls: String(q.value.cls || ""), asc: list(q.value.asc), dmg: list(q.value.dmg), weapon: list(q.value.weapon),
    tag: list(q.value.tag), patch: q.value.patch === "all" ? "all" : "current", text: String(q.value.q || ""),
    sort: String(q.value.sort || "rating"), view: q.value.view === "list" ? "list" : "grid", n: Number(q.value.n) || PAGE,
  }));
  // a change of the filters keeps the page where it is (no jump to the top)
  const set = (patch: Record<string, string | string[] | number | undefined>) => {
    const next: Record<string, unknown> = { ...q.value, ...patch };
    for (const [k, v] of Object.entries(next)) if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) delete next[k];
    if (!("n" in patch)) delete next.n;
    router.replace({ query: next as Record<string, string> });
  };
  const toggle = (key: "asc" | "dmg" | "weapon" | "tag", value: string) => {
    const cur = state.value[key];
    set({ [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] });
  };

  // the words typed: the known ones as filters, the rest searched in the title, skill, class and tags
  const words = computed(() => state.value.text.split(/\s+/).filter(Boolean));
  const free = computed(() => words.value.filter((w) => !knownWord(w)));
  const matches = (b: BuildCard, s = state.value) => {
    if (s.cls && b.cls !== s.cls) return false;
    if (s.asc.length && !s.asc.includes(b.asc)) return false;
    if (s.dmg.length && !s.dmg.includes(b.dmg)) return false;
    if (s.weapon.length && !s.weapon.includes(b.weapon)) return false;
    if (s.tag.some((t) => !b.tags.includes(t))) return false;
    if (s.patch === "current" && b.patch !== CURRENT_PATCH) return false;
    for (const w of words.value) {
      const k = knownWord(w);
      if (k?.kind === "tag" && !b.tags.includes(k.key)) return false;
      if (k?.kind === "dmg" && b.dmg !== k.key) return false;
      if (k?.kind === "weapon" && b.weapon !== k.key) return false;
      if (k?.kind === "cls" && b.cls !== k.key) return false;
    }
    const hay = norm([b.title, b.skill, b.asc, CLASSES.find((c) => c.key === b.cls)?.name, b.weapon, ...b.tags].join(" "));
    return free.value.every((w) => hay.includes(norm(w)));
  };
  const found = computed(() => {
    const out = BUILDS.filter((b) => matches(b));
    const by: Record<string, (a: BuildCard, b: BuildCard) => number> = {
      rating: (a, b) => b.rating - a.rating || b.reviews - a.reviews, popular: (a, b) => b.opens - a.opens,
      new: (a, b) => b.updated.localeCompare(a.updated), dps: (a, b) => b.dps - a.dps };
    return out.sort(by[state.value.sort] || by.rating);
  });
  // how many builds a choice would give with everything else as it is (the numbers beside the ascendancies)
  const countWith = (patch: Partial<typeof state.value>) => BUILDS.filter((b) => matches(b, { ...state.value, ...patch })).length;
  // the filters applied, each to remove on its own
  const applied = computed(() => {
    const s = state.value, out: { label: string; icon?: string; color?: string; cls?: string; drop: () => void }[] = [];
    if (s.cls) out.push({ label: [CLASSES.find((c) => c.key === s.cls)?.name, ...s.asc].join(" · "), cls: s.cls, drop: () => set({ cls: undefined, asc: undefined }) });
    for (const d of s.dmg) { const x = DMG.find((y) => y.key === d)!; out.push({ label: x.name, icon: x.icon, color: `var(--${d})`, drop: () => toggle("dmg", d) }); }
    for (const w of s.weapon) out.push({ label: w, drop: () => toggle("weapon", w) });
    for (const t of s.tag) out.push({ label: t, drop: () => toggle("tag", t) });
    return out;
  });
  return { state, set, toggle, found, countWith, applied, words, knownWord };
}
