<script setup lang="ts">
// One review: who wrote it (their character), stars, criteria, the text, "helpful" (one vote, a toggle), the
// build's author's answer; on an author's page also which build it is about.
import type { Review } from "~~/mock/page";
import type { BuildCard } from "~~/mock/builds";
const props = defineProps<{ r: Review; author: { nick: string; hue: number }; on?: BuildCard }>();
const voted = ref(!!props.r.voted);
const count = computed(() => props.r.helpful + (voted.value ? 1 : 0) - (props.r.voted ? 1 : 0));
</script>

<template>
  <article class="rv">
    <Ava :nick="r.nick" :hue="r.hue" />
    <div style="min-width: 0">
      <div class="rv-h"><b>{{ r.nick }}</b><span class="rv-char"><span :class="['cls', `k-${r.cls}`]"><Ic :name="`c-${r.cls}`" /></span>{{ r.clsName }} · {{ r.level }} ур.</span>
        <Stars :r="r.stars" /><span class="rv-date">{{ r.when }}</span></div>
      <NuxtLink v-if="on" class="rv-on" :to="`/b/${on.id}`"><BuildArt :b="on" cls="gi gi-s" />к билду «{{ on.title }}»</NuxtLink>
      <div v-if="r.crit" class="rv-crit"><span v-for="[k, v] in r.crit" :key="k">{{ k }} <b>{{ v }}</b></span></div>
      <p class="rv-t">{{ r.text }}</p>
      <div class="rv-f">
        <button :class="['btn', 'btn-quiet', { 'is-on': voted }]" type="button" :aria-pressed="voted" @click="voted = !voted"><Ic name="thumb" />Полезно · {{ count }}</button>
        <button class="btn btn-quiet" type="button" aria-label="Пожаловаться на отзыв"><Ic name="flag" /></button></div>
      <div v-if="r.reply" class="rv-reply">
        <div class="rv-h"><Ava :nick="author.nick" :hue="author.hue" size="xs" /><b>{{ author.nick }}</b><span class="badge gold">автор</span><span class="rv-date">{{ r.reply.when }}</span></div>
        <p class="rv-t">{{ r.reply.text }}</p>
      </div>
    </div>
  </article>
</template>
