<script setup lang="ts">
// The catalog: filters on the left (a sheet on a phone), the search words as plates, the builds found as cards or
// lines, "show more"; everything in the address.
import { DMG } from "~~/mock/builds";

const { state, set, found, applied, words, knownWord } = useCatalog();
const shown = computed(() => found.value.slice(0, state.value.n));
const left = computed(() => Math.max(0, found.value.length - shown.value.length));

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
useHead({ title: "Каталог билдов — poe2lab" });
</script>

<template>
  <div class="wrap">
    <nav class="crumbs" aria-label="Путь"><NuxtLink to="/">Главная</NuxtLink><Ic name="chev-r" /><span>Каталог билдов</span></nav>
    <div class="cat">
      <aside class="fpanel" aria-label="Фильтры"><CatalogFilters /></aside>

      <section aria-label="Найденные билды">
        <div class="cat-top">
          <label class="search lg" style="height: 50px; box-shadow: none"><Ic name="search" />
            <span v-for="p in plates" :key="p.w" class="qtok"><Ic v-if="plateIcon(p.k)" :name="plateIcon(p.k)!" />{{ p.k!.name }}</span>
            <input v-model="draft" type="search" :placeholder="plates.length ? 'Добавь ещё слово или тег' : 'Скилл, класс или тег'" aria-label="Поиск билдов"
              @input="onInput" @keydown="onBack" @keydown.enter="commit(draft)" />
            <button v-if="words.length" class="btn btn-sm btn-quiet" type="button" aria-label="Очистить поиск" @click="clear"><Ic name="x" /></button></label>
          <div class="cat-bar">
            <span class="found">Найдено <b>{{ found.length }}</b> {{ plural(found.length, "билд", "билда", "билдов") }}</span>
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

        <div v-if="!found.length" class="empty card">
          <Ic name="search" /><b>Ничего не нашли</b>
          <span>Сними какой-нибудь фильтр — или напиши по-другому: по названию, скиллу или тегу.</span>
          <div v-if="applied.length" class="chips" style="justify-content: center">
            <span v-for="a in applied" :key="a.label" class="chip applied">{{ a.label }}<button class="x" type="button" aria-label="Убрать" @click="a.drop()"><Ic name="x" /></button></span>
          </div>
        </div>
        <template v-else>
          <div v-if="state.view === 'grid'" class="bgrid no-phone"><BuildTile v-for="b in shown" :key="b.id" :b="b" /></div>
          <div :class="['blist', state.view === 'grid' ? 'only-phone' : '']"><BuildRow v-for="b in shown" :key="b.id" :b="b" /></div>
          <div v-if="left" class="more">
            <button class="btn btn-ghost btn-lg" type="button" @click="set({ n: state.n + PAGE })">Показать ещё<span class="faint">· {{ left }}</span></button>
            <small>Показано {{ shown.length }} из {{ found.length }}</small>
          </div>
        </template>
      </section>
    </div>

    <template v-if="sheet">
      <div class="sheet-back" @click="sheet = false" />
      <div class="sheet" role="dialog" aria-label="Фильтры">
        <div class="sheet-grab" />
        <div class="sheet-h"><b>Фильтры</b><span v-if="applied.length" class="badge gold">{{ applied.length }}</span><span class="spacer" />
          <button class="icon-btn" type="button" aria-label="Закрыть" @click="sheet = false"><Ic name="x" /></button></div>
        <div class="sheet-b"><CatalogFilters /></div>
        <div class="sheet-f"><button class="btn btn-quiet" type="button" @click="set({ cls: undefined, asc: undefined, dmg: undefined, weapon: undefined, tag: undefined })">Сбросить</button>
          <button class="btn btn-primary" type="button" @click="sheet = false">Показать {{ found.length }} {{ plural(found.length, "билд", "билда", "билдов") }}</button></div>
      </div>
    </template>
  </div>
</template>
