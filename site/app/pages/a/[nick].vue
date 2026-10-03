<script setup lang="ts">
// An author's public page: who, links, numbers, "follow", the builds (sorted), the latest reviews on them.
import { BUILDS } from "~~/mock/builds";
import { profileOf } from "~~/mock/authors";

const route = useRoute();
const nick = computed(() => String(route.params.nick));
const builds = computed(() => BUILDS.filter((b) => b.author === nick.value));
const a = computed(() => profileOf(nick.value, builds.value[0]?.hue));
const avg = computed(() => (builds.value.length ? builds.value.reduce((s, b) => s + b.rating, 0) / builds.value.length : 0));
const sort = ref<"rating" | "new" | "popular">("rating");
const sorted = computed(() => [...builds.value].sort(sort.value === "new" ? (x, y) => y.updated.localeCompare(x.updated)
  : sort.value === "popular" ? (x, y) => y.opens - x.opens : (x, y) => y.rating - x.rating));
const following = ref(false);
const thousands = (n: number) => (n >= 1000 ? `${fmtRating(n / 1000)} тыс.` : String(n));
useHead(() => ({ title: `${nick.value} — авторы poe2lab` }));
</script>

<template>
  <div class="wrap">
    <nav class="crumbs" aria-label="Путь"><NuxtLink to="/">Главная</NuxtLink><Ic name="chev-r" /><NuxtLink to="/">Авторы</NuxtLink><Ic name="chev-r" /><span>{{ nick }}</span></nav>
    <header class="phead">
      <Ava :nick="a.nick" :hue="a.hue" size="xl" />
      <div style="min-width: 0">
        <h1>{{ a.nick }}<span v-if="a.top" class="badge gold"><Ic name="crown" />в топе авторов</span></h1>
        <p v-if="a.bio">{{ a.bio }}</p>
        <div class="links">
          <a v-for="l in a.links" :key="l.label" :href="l.href"><Ic :name="l.icon" />{{ l.label }}</a>
          <span class="faint" style="font-size: 12.5px; align-self: center">на сайте {{ a.since }}</span>
        </div>
      </div>
      <div class="pside">
        <div class="pstats">
          <div class="pstat"><b>{{ builds.length }}</b><small>{{ plural(builds.length, "билд", "билда", "билдов") }}</small></div>
          <div class="pstat"><b>{{ avg ? fmtRating(avg) : "—" }}</b><small>оценка</small></div>
          <div class="pstat"><b>{{ thousands(a.followers + (following ? 1 : 0)) }}</b><small>подписчиков</small></div>
        </div>
        <button v-if="following" class="btn btn-lg follow is-on" type="button" @click="following = false"><Ic name="check" />Вы подписаны</button>
        <button v-else class="btn btn-primary btn-lg follow" type="button" @click="following = true"><Ic name="plus" />Подписаться</button>
      </div>
    </header>

    <div class="shead" style="margin-top: 10px"><div><h2><Ic name="grid4" />Билды<span class="faint" style="font-weight: 500">{{ builds.length }}</span></h2></div>
      <div class="seg soft" role="group" aria-label="Сортировка">
        <button v-for="[k, n] in [['rating', 'По рейтингу'], ['new', 'Новые'], ['popular', 'Популярные']] as const" :key="k" :class="{ 'is-on': sort === k }" type="button" @click="sort = k">{{ n }}</button></div></div>
    <div v-if="sorted.length" class="bgrid"><BuildTile v-for="b in sorted" :key="b.id" :b="b" /></div>
    <div v-else class="empty card"><Ic name="grid4" /><b>Пока нет опубликованных билдов</b></div>

    <template v-if="a.reviews.length">
      <div class="shead"><div><h2><Ic name="chat" />Отзывы на билды автора<span class="faint" style="font-weight: 500">{{ a.reviewsTotal }}</span></h2><p>Последние отзывы на все билды {{ a.nick }}</p></div></div>
      <div class="rv-list" style="max-width: 920px">
        <ReviewCard v-for="r in a.reviews" :key="r.nick" :r="r" :author="{ nick: a.nick, hue: a.hue }" :on="BUILDS.find((b) => b.id === r.build)" />
      </div>
    </template>
  </div>
</template>
