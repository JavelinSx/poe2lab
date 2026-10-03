<script setup lang="ts">
// A build as a line of the list view: easy to compare the numbers.
import type { BuildCard } from "~~/mock/builds";
const props = defineProps<{ b: BuildCard }>();
const defLabel = computed(() => (props.b.es ? "ЗД + ЭЩ" : "Здоровье"));
</script>

<template>
  <NuxtLink class="br" :to="`/b/${b.id}`">
    <span class="gframe"><BuildArt :b="b" /></span>
    <div class="br-t"><b>{{ b.title }}</b><ClsLine :cls="b.cls" :asc="b.asc" />
      <span class="m-nums only-phone"><span>DPS <b>{{ fmtInt(b.dps) }}</b></span><span>{{ defLabel }} <b>{{ fmtInt(b.life) }}<template v-if="b.es"><span class="plus">+</span>{{ fmtInt(b.es) }}</template></b></span></span></div>
    <div class="bc-tags"><span v-for="t in b.tags.slice(0, 3)" :key="t" class="tag">{{ t }}</span></div>
    <div class="br-n dps"><b>{{ fmtInt(b.dps) }}</b><small>DPS</small></div>
    <div class="br-n def"><b>{{ fmtInt(b.life) }}<template v-if="b.es"><span class="plus">+</span>{{ fmtInt(b.es) }}</template></b><small>{{ defLabel }}</small></div>
    <div class="br-a"><Ava :nick="b.author" :hue="b.hue" size="xs" /><span>{{ b.author }}</span></div>
    <div class="br-r"><span class="rate"><Stars :r="b.rating" /><b>{{ fmtRating(b.rating) }}</b></span><PatchBadge :patch="b.patch" :old="b.old" /></div>
  </NuxtLink>
</template>
