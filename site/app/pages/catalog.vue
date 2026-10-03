<script setup lang="ts">
// The catalog: filters on the left (a sheet on a phone), the search words as plates, the builds found as cards or
// lines, "show more"; everything in the address. The builds come from the API; while the first answer is on its way,
// the cards' skeletons; a later change keeps the cards shown (dimmed) until the new ones come.
import { DMG } from "~~/shared/catalog";

const { state, set, applied, words, knownWord } = useCatalog();
const { data, status, error, refresh } = useCatalogResults();
const shown = computed(() => data.value.builds);
const total = computed(() => data.value.total);
const left = computed(() => Math.max(0, total.value - shown.value.length));
const first = computed(() => status.value === "pending" && !shown.value.length);
const me = useMe();

// the search field: the known words as plates, the rest typed; Backspace in an empty field takes the last plate off
const plates = computed(() => words.value.map((w) => ({ w, k: knownWord(w) })).filter((x) => x.k));
const draft = ref(words.value.filter((w) => !knownWord(w)).join(" "));
const commit = (text: string) => {
  const typed = text.split(/\s+/).filter(Boolean);
  set({ q: [...plates.value.map((p) => p.w), ...typed].join(" ") || undefined });
};
let timer: ReturnType<typeof setTimeout> | undefined;
function onInput() {
  clearTimeout(timer);
  // a finished word that is a tag, a damage type, a weapon or a class becomes a plate at once
  if (/\s$/.test(draft.value) && draft.value.trim().split(/\s+/).some((w) => knownWord(w))) {
    commit(draft.value);
    draft.value = draft.value.trim().split(/\s+/).filter((w) => !knownWord(w)).join(" ");
    return;
  }
  timer = setTimeout(() => commit(draft.value), 200);
}
function onBack(e: KeyboardEvent) {
  if (e.key === "Backspace" && !draft.value && plates.value.length) {
    e.preventDefault();
    set({ q: plates.value.slice(0, -1).map((p) => p.w).join(" ") || undefined });
  }
}
const clear = () => { draft.value = ""; set({ q: undefined }); };
const plateIcon = (k: ReturnType<typeof knownWord>) => (k?.kind === "dmg" ? DMG.find((d) => d.key === k.key)?.icon : undefined);

// the phone's sheet: its changes add up and apply on "show N builds" (here they apply at once; the button closes it)
const sheet = ref(false);
const sorts = SORTS;
useHead(() => ({ title: state.value.fav ? "Избранное — poe2lab" : "Каталог билдов — poe2lab" }));
</script>

<template>
  <div class="wrap">
    <nav class="crumbs" aria-label="Путь"><NuxtLink to="/">Главная</NuxtLink><Ic name="chev-r" /><span>{{ state.fav ? "Избранное" : "Каталог билдов" }}</span></nav>
    <div class="cat">
      <aside class="fpanel" aria-label="Фильтры"><CatalogFilters :counts="data.ascendancies" /></aside>

      <section aria-label="Найденные билды">
        <div class="cat-top">
          <label class="search lg" style="height: 50px; box-shadow: none"><Ic name="search" />
            <span v-for="p in plates" :key="p.w" class="qtok"><Ic v-if="plateIcon(p.k)" :name="plateIcon(p.k)!" />{{ p.k!.name }}</span>
            <input v-model="draft" type="search" :placeholder="plates.length ? 'Добавь ещё слово или тег' : 'Скилл, класс или тег'" aria-label="Поиск билдов"
              @input="onInput" @keydown="onBack" @keydown.enter="commit(draft)" />
            <button v-if="words.length" class="btn btn-sm btn-quiet" type="button" aria-label="Очистить поиск" @click="clear"><Ic name="x" /></button></label>
          <div class="cat-bar">
            <span class="found">Найдено <b>{{ total }}</b> {{ plural(total, "билд", "билда", "билдов") }}</span>
            <button class="btn btn-sm btn-ghost only-phone" type="button" @click="sheet = true"><Ic name="sliders" />Фильтры
              <span v-if="applied.length" class="pill-n gold" style="height: 18px; min-width: 18px; font-size: 11px">{{ applied.length }}</span></button>
            <span v-for="a in applied" :key="a.label" class="chip applied no-phone">
              <span v-if="a.cls" :class="['cls', `k-${a.cls}`]" style="width: 18px; height: 18px; margin-left: -6px"><Ic :name="`c-${a.cls}`" /></span>
              <Ic v-if="a.icon" :name="a.icon" :style="{ color: a.color }" />{{ a.label }}
              <button class="x" type="button" aria-label="Убрать" @click="a.drop()"><Ic name="x" /></button></span>
            <span class="spacer" />
            <label class="fsel" style="color: var(--text-2)"><Ic name="sort" style="color: var(--faint)" />
              <select :value="state.sort" aria-label="Сортировка" @change="set({ sort: ($event.target as HTMLSelectElement).value })">
                <option v-for="s in sorts" :key="s.key" :value="s.key">{{ s.name }}</option></select></label>
            <div class="seg no-phone" role="group" aria-label="Вид">
              <button :class="{ 'is-on': state.view === 'grid' }" type="button" aria-label="Сеткой" @click="set({ view: undefined })"><Ic name="grid4" /></button>
              <button :class="{ 'is-on': state.view === 'list' }" type="button" aria-label="Списком" @click="set({ view: 'list' })"><Ic name="list" /></button>
            </div>
          </div>
        </div>

        <StatePanel v-if="state.fav && !me" icon="star-o" title="Избранное — после входа" text="Отмечай билды звёздочкой, и они соберутся здесь.">
          <NuxtLink class="btn btn-primary" :to="{ path: '/login', query: { next: '/catalog?fav=1' } }"><Ic name="login" />Войти</NuxtLink>
        </StatePanel>
        <LoadError v-else-if="error && !shown.length" :error="error" @retry="refresh()" />
        <div v-else-if="first" class="bgrid"><BuildSkel v-for="i in 6" :key="i" /></div>
        <StatePanel v-else-if="state.fav && !total && !applied.slice(1).length && !state.text" icon="star-o" title="В избранном пусто"
          text="Открой билд и нажми «В избранное» — он появится здесь.">
          <NuxtLink class="btn btn-primary" to="/catalog"><Ic name="grid4" />В каталог</NuxtLink>
        </StatePanel>
        <StatePanel v-else-if="!total" icon="search" title="Ничего не нашли"
          :text="state.text ? `По запросу «${state.text}» с этими фильтрами билдов нет. Убери один фильтр:` : 'С этими фильтрами билдов нет. Убери один фильтр:'">
          <div v-if="applied.length" class="chips" style="justify-content: center">
            <span v-for="a in applied" :key="a.label" class="chip applied">{{ a.label }}<button class="x" type="button" aria-label="Убрать" @click="a.drop()"><Ic name="x" /></button></span>
          </div>
          <button class="btn btn-quiet" type="button" @click="clear(); set({ cls: undefined, asc: undefined, dmg: undefined, weapon: undefined, tag: undefined, patch: undefined, fav: undefined })">Сбросить всё</button>
        </StatePanel>
        <div v-else :style="status === 'pending' ? { opacity: 0.55, transition: 'opacity .2s' } : undefined">
          <div v-if="state.view === 'grid'" class="bgrid no-phone"><BuildTile v-for="b in shown" :key="b.id" :b="b" /></div>
          <div :class="['blist', state.view === 'grid' ? 'only-phone' : '']"><BuildRow v-for="b in shown" :key="b.id" :b="b" /></div>
          <div v-if="left" class="more">
            <button class="btn btn-ghost btn-lg" type="button" @click="set({ n: state.n + PAGE })">Показать ещё<span class="faint">· {{ left }}</span></button>
            <small>Показано {{ shown.length }} из {{ total }}</small>
          </div>
        </div>
      </section>
    </div>

    <template v-if="sheet">
      <div class="sheet-back" @click="sheet = false" />
      <div class="sheet" role="dialog" aria-label="Фильтры">
        <div class="sheet-grab" />
        <div class="sheet-h"><b>Фильтры</b><span v-if="applied.length" class="badge gold">{{ applied.length }}</span><span class="spacer" />
          <button class="icon-btn" type="button" aria-label="Закрыть" @click="sheet = false"><Ic name="x" /></button></div>
        <div class="sheet-b"><CatalogFilters :counts="data.ascendancies" /></div>
        <div class="sheet-f"><button class="btn btn-quiet" type="button" @click="set({ cls: undefined, asc: undefined, dmg: undefined, weapon: undefined, tag: undefined })">Сбросить</button>
          <button class="btn btn-primary" type="button" @click="sheet = false">Показать {{ total }} {{ plural(total, "билд", "билда", "билдов") }}</button></div>
      </div>
    </template>
  </div>
</template>
