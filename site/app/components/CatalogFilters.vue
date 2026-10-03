<script setup lang="ts">
// The catalog's filters: in the side panel on a computer, in the bottom sheet on a phone. A choice applies at once.
// `counts`: how many builds each ascendancy of the chosen class gives with the other filters as they are.
import { CLASSES, CURRENT_PATCH, DMG, TAGS, WEAPONS } from "~~/shared/catalog";
defineProps<{ counts: Record<string, number> }>();
const { state, set, toggle } = useCatalog();
const skill = ref(state.value.text);
const cls = computed(() => CLASSES.find((c) => c.key === state.value.cls));
const pickClass = (k: string) => set({ cls: state.value.cls === k ? undefined : k, asc: undefined });
let timer: ReturnType<typeof setTimeout> | undefined;
watch(skill, (v) => { clearTimeout(timer); timer = setTimeout(() => set({ q: v.trim() || undefined }), 200); });
</script>

<template>
  <div class="fgrp">
    <div class="fgrp-t">Класс <a v-if="state.cls" href="#" @click.prevent="set({ cls: undefined, asc: undefined })">сбросить</a></div>
    <div class="clsgrid">
      <button v-for="c in CLASSES" :key="c.key" :class="['clsb', `k-${c.key}`, { 'is-on': state.cls === c.key }]" type="button"
        :aria-pressed="state.cls === c.key" @click="pickClass(c.key)"><span class="cls"><Ic :name="`c-${c.key}`" /></span>{{ c.name }}</button>
    </div>
    <div v-if="cls" class="asclist">
      <label v-for="a in cls.ascs" :key="a" :class="['ascr', { 'is-on': state.asc.includes(a) }]" @click.prevent="toggle('asc', a)">
        <span class="cbox"><Ic v-if="state.asc.includes(a)" name="check" /></span>{{ a }}<span class="n">{{ counts[a] ?? 0 }}</span></label>
    </div>
  </div>
  <div class="fgrp">
    <div class="fgrp-t">Главный скилл</div>
    <label class="search"><Ic name="search" /><input v-model="skill" type="search" placeholder="Название или теги скилла" aria-label="Главный скилл" /></label>
  </div>
  <div class="fgrp">
    <div class="fgrp-t">Тип урона</div>
    <div class="chips">
      <button v-for="d in DMG" :key="d.key" :class="['chip', 'sm', 'dmg', { 'is-on': state.dmg.includes(d.key) }]" type="button"
        :style="{ '--c': `var(--${d.key})` }" @click="toggle('dmg', d.key)"><Ic :name="d.icon" />{{ d.name }}</button>
    </div>
  </div>
  <div class="fgrp">
    <div class="fgrp-t">Оружие</div>
    <div class="chips">
      <button v-for="w in WEAPONS" :key="w" :class="['chip', 'sm', { 'is-on': state.weapon.includes(w) }]" type="button" @click="toggle('weapon', w)">{{ w }}</button>
    </div>
  </div>
  <div class="fgrp">
    <div class="fgrp-t">Теги</div>
    <div class="chips">
      <button v-for="t in TAGS" :key="t.name" :class="['chip', 'sm', { 'is-on': state.tag.includes(t.name) }]" type="button" @click="toggle('tag', t.name)"><Ic :name="t.icon" />{{ t.name }}</button>
    </div>
  </div>
  <div class="fgrp">
    <div class="fgrp-t">Патч</div>
    <div class="seg soft">
      <button :class="{ 'is-on': state.patch === 'current' }" type="button" @click="set({ patch: undefined })">текущий {{ CURRENT_PATCH }}</button>
      <button :class="{ 'is-on': state.patch === 'all' }" type="button" @click="set({ patch: 'all' })">все</button>
    </div>
    <p class="hint" style="margin-top: 8px">Билды старых патчей могут считаться иначе — у них жёлтый значок.</p>
  </div>
</template>
