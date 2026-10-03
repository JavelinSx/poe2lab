<script setup lang="ts">
// A build in the catalog and the shelves: its skill and class, two numbers, the rating, the author, the patch.
import type { BuildCard } from "~~/mock/builds";
const props = defineProps<{ b: BuildCard }>();
const defLabel = computed(() => (props.b.es ? "ЗД + ЭЩ" : "Здоровье"));
</script>

<template>
  <NuxtLink :class="['bc', `t-${b.dmg}`]" :to="`/b/${b.id}`">
    <div class="bc-top">
      <img class="bc-cover" :src="gameArt(b.cover)" alt="" loading="lazy" />
      <span class="gframe"><BuildArt :b="b" /></span>
      <div class="bc-skill"><span>{{ b.skill }}</span><ClsLine :cls="b.cls" :asc="b.asc" /></div>
    </div>
    <div class="bc-b">
      <h3 class="bc-t">{{ b.title }}</h3>
      <div class="bc-nums">
        <span class="bn dps"><small><Ic name="sword" />DPS</small><b>{{ fmtInt(b.dps) }}</b></span>
        <span class="bn def"><small><Ic :name="b.es ? 'shield' : 'heart'" />{{ defLabel }}</small>
          <b>{{ fmtInt(b.life) }}<template v-if="b.es"><span class="plus">+</span>{{ fmtInt(b.es) }}</template></b></span>
      </div>
      <div class="rate"><Stars :r="b.rating" /><b>{{ fmtRating(b.rating) }}</b><span>· {{ b.reviews }} отз.</span></div>
      <div class="bc-tags"><span v-for="t in b.tags.slice(0, 3)" :key="t" class="tag">{{ t }}</span></div>
    </div>
    <div class="bc-f"><Ava :nick="b.author" :hue="b.hue" size="xs" /><span class="who-n">{{ b.author }}</span><span class="spacer" /><PatchBadge :patch="b.patch" :old="b.old" /></div>
  </NuxtLink>
</template>
