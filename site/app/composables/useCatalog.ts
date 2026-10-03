// The catalog's state lives in the page's address (a selection can be shared by its link): the class and its
// ascendancies, damage types, weapons, tags, the patch, the search words, the sort, the view, how many are shown and
// whether it is the favourites. The builds themselves come from /api/builds (useCatalogResults).
import { CLASSES, DMG, knownWord } from "~~/shared/catalog";
import type { CatalogData } from "~~/shared/api";

export const PAGE = 24;
export const SORTS = [{ key: "rating", name: "По рейтингу" }, { key: "popular", name: "Популярные" },
  { key: "new", name: "Новые" }, { key: "dps", name: "По урону" }] as const;

const list = (v: unknown) => (Array.isArray(v) ? v : v ? [v] : []).map(String).filter(Boolean);

export function useCatalog() {
  const route = useRoute();
  const router = useRouter();
  const q = computed(() => route.query);
  const state = computed(() => ({
    cls: String(q.value.cls || ""), asc: list(q.value.asc), dmg: list(q.value.dmg), weapon: list(q.value.weapon),
    tag: list(q.value.tag), patch: q.value.patch === "all" ? "all" : "current", text: String(q.value.q || ""),
    sort: String(q.value.sort || "rating"), view: q.value.view === "list" ? "list" : "grid", n: Number(q.value.n) || PAGE,
    fav: q.value.fav === "1",
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
  const words = computed(() => state.value.text.split(/\s+/).filter(Boolean));
  // the filters applied, each to remove on its own
  const applied = computed(() => {
    const s = state.value, out: { label: string; icon?: string; color?: string; cls?: string; drop: () => void }[] = [];
    if (s.fav) out.push({ label: "избранное", icon: "star", color: "var(--gold)", drop: () => set({ fav: undefined }) });
    if (s.cls) out.push({ label: [CLASSES.find((c) => c.key === s.cls)?.name, ...s.asc].join(" · "), cls: s.cls, drop: () => set({ cls: undefined, asc: undefined }) });
    for (const d of s.dmg) { const x = DMG.find((y) => y.key === d)!; out.push({ label: x.name, icon: x.icon, color: `var(--${d})`, drop: () => toggle("dmg", d) }); }
    for (const w of s.weapon) out.push({ label: w, drop: () => toggle("weapon", w) });
    for (const t of s.tag) out.push({ label: t, drop: () => toggle("tag", t) });
    return out;
  });
  return { state, set, toggle, applied, words, knownWord };
}

/** The builds for the address's filters: as many as shown ("show more" asks for more), the total, the ascendancies' counts. */
export function useCatalogResults() {
  const { state } = useCatalog();
  const query = computed(() => {
    const s = state.value;
    return { cls: s.cls || undefined, asc: s.asc, dmg: s.dmg, weapon: s.weapon, tag: s.tag, patch: s.patch === "all" ? "all" : undefined,
      q: s.text || undefined, sort: s.sort, limit: s.n, fav: s.fav ? "1" : undefined };
  });
  return useFetch<CatalogData>("/api/builds", { key: "catalog", query, default: () => ({ builds: [], total: 0, offset: 0, ascendancies: {} }) });
}
