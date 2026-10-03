<script setup lang="ts">
// An author's public page: who, links, numbers, "follow", the builds (sorted), the latest reviews on them
// (/api/authors/:nick).
import { LINK_KINDS, type AuthorPage } from "~~/shared/api";

const route = useRoute();
const nick = computed(() => String(route.params.nick));
const { data: a, error, refresh } = useFetch<AuthorPage>(() => `/api/authors/${encodeURIComponent(nick.value)}`, { key: `author-${nick.value}` });
const builds = computed(() => a.value?.builds ?? []);
const rated = computed(() => builds.value.filter((b) => b.reviews));
const avg = computed(() => rated.value.reduce((s, b) => s + b.rating * b.reviews, 0) / Math.max(1, rated.value.reduce((s, b) => s + b.reviews, 0)));
const sort = ref<"rating" | "new" | "popular">("rating");
const sorted = computed(() => [...builds.value].sort(sort.value === "new" ? (x, y) => y.updated.localeCompare(x.updated)
  : sort.value === "popular" ? (x, y) => y.opens - x.opens : (x, y) => y.rating - x.rating || y.reviews - x.reviews));
const thousands = (n: number) => (n >= 1000 ? `${fmtRating(n / 1000)} тыс.` : String(n));
const me = useMe();
const toast = useToast();
const needLogin = useNeedLogin();
const self = computed(() => me.value?.nick.toLowerCase() === a.value?.nick.toLowerCase());
async function toggleFollow() {
  if (!me.value) return needLogin("Подписаться на автора");
  const on = !a.value!.following;
  try {
    await $fetch(`/api/follows/${encodeURIComponent(a.value!.nick)}`, { method: on ? "POST" : "DELETE" });
    a.value = { ...a.value!, following: on, followers: a.value!.followers + (on ? 1 : -1) };
    if (on) toast("Новые билды автора придут в уведомления");
  } catch (e) { toast(apiError(e), { bad: true }); }
}
useHead(() => ({ title: `${a.value?.nick ?? nick.value} — авторы poe2lab` }));
</script>

<template>
  <div v-if="apiStatus(error) === 404" class="wrap" style="padding: 40px 0; max-width: 620px">
    <StatePanel code="404" title="Такого автора нет" text="Возможно, он сменил ник или удалил аккаунт.">
      <div class="row"><NuxtLink class="btn btn-primary" to="/catalog"><Ic name="grid4" />В каталог</NuxtLink><NuxtLink class="btn btn-quiet" to="/">На главную</NuxtLink></div>
    </StatePanel>
  </div>
  <div v-else-if="error" class="wrap" style="padding: 40px 0; max-width: 620px"><LoadError :error="error" @retry="refresh()" /></div>
  <div v-else-if="!a" class="wrap" style="padding: 40px 0"><div class="panel" style="padding: 22px; display: flex; gap: 16px; align-items: center">
    <span class="skel circle" style="width: 80px; height: 80px; flex: none" /><div style="flex: 1; display: flex; flex-direction: column; gap: 10px">
      <span class="skel" style="height: 18px; width: 40%" /><span class="skel" style="width: 70%" /></div></div></div>
  <div v-else class="wrap">
    <nav class="crumbs" aria-label="Путь"><NuxtLink to="/">Главная</NuxtLink><Ic name="chev-r" /><NuxtLink to="/#authors">Авторы</NuxtLink><Ic name="chev-r" /><span>{{ a.nick }}</span></nav>
    <header class="phead">
      <Ava :nick="a.nick" :hue="a.hue" :src="a.avatar ?? undefined" size="xl" />
      <div style="min-width: 0">
        <h1>{{ a.nick }}</h1>
        <p v-if="a.bio">{{ a.bio }}</p>
        <div class="links">
          <a v-for="l in a.links" :key="l.url" :href="l.url" rel="noopener nofollow" target="_blank"><Ic :name="LINK_KINDS[l.kind].icon" />{{ LINK_KINDS[l.kind].label }}</a>
          <span class="faint" style="font-size: 12.5px; align-self: center">на сайте {{ fmtSince(a.since) }}</span>
        </div>
      </div>
      <div class="pside">
        <div class="pstats">
          <div class="pstat"><b>{{ builds.length }}</b><small>{{ plural(builds.length, "билд", "билда", "билдов") }}</small></div>
          <div class="pstat"><b>{{ rated.length ? fmtRating(avg) : "—" }}</b><small>оценка</small></div>
          <div class="pstat"><b>{{ thousands(a.followers) }}</b><small>{{ plural(a.followers, "подписчик", "подписчика", "подписчиков") }}</small></div>
        </div>
        <NuxtLink v-if="self" class="btn btn-lg" to="/me/settings#settings"><Ic name="edit" />Изменить профиль</NuxtLink>
        <button v-else-if="a.following" class="btn btn-lg follow is-on" type="button" @click="toggleFollow"><Ic name="check" />Вы подписаны</button>
        <button v-else class="btn btn-primary btn-lg follow" type="button" @click="toggleFollow"><Ic name="plus" />Подписаться</button>
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
        <ReviewCard v-for="r in a.reviews" :key="r.id" :r="r" :author="{ nick: a.nick, hue: a.hue, avatar: a.avatar }" :on="builds.find((b) => b.id === r.build)" :can-reply="self" />
      </div>
    </template>
  </div>
</template>
