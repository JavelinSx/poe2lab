<script setup lang="ts">
// A search result: the thing's picture, name and kind, its tags (the ones the query found it by lit); it can be
// dragged into the text or clicked.
import { KIND_LABEL, type GameThing } from "~~/mock/game";
const props = defineProps<{ g: GameThing; q: string; on?: boolean; grip?: boolean }>();
const tags = computed(() => [...props.g.tags.filter((t) => tagHit(t, props.q)), ...props.g.tags.filter((t) => !tagHit(t, props.q))].slice(0, 5));
const drag = (e: DragEvent) => { e.dataTransfer?.setData("application/x-poe2lab-token", props.g.key); e.dataTransfer?.setData("text/plain", `[[${props.g.key}]]`); };
</script>

<template>
  <div :class="['rr', { 'is-on': on }]" :draggable="grip ? 'true' : undefined" @dragstart="drag" @mousedown.prevent>
    <img v-if="g.card.img" :src="gameArt(g.card.img)" alt="" :style="g.kind === 'support' ? 'border-radius: 50%' : undefined" />
    <span v-else-if="g.card.ph" class="gph" :style="{ '--c': `var(--${g.card.ph})` }"><Ic :name="g.card.ph === 'light' ? 'bolt' : g.card.ph" /></span>
    <span v-else class="gph"><Ic name="book" /></span>
    <span><span class="rr-n">{{ g.card.name }}<small>{{ KIND_LABEL[g.kind] }}</small></span>
      <span class="rr-tags"><span v-for="t in tags" :key="t" :class="['tg', { hit: tagHit(t, q) }]">{{ t }}</span></span></span>
    <Ic v-if="grip" name="grip" />
    <slot />
  </div>
</template>
