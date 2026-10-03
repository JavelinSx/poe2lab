<script setup lang="ts">
// The main page: what the site is, the search, the classes, the shelves, the best authors, the app. The numbers,
// shelves and authors come from /api/home in one answer.
import { CLASSES } from "~~/shared/catalog";
import type { HomeData } from "~~/shared/api";

const router = useRouter();
const q = ref("");
const find = (text = q.value) => router.push({ path: "/catalog", query: text.trim() ? { q: text.trim() } : {} });
const { data, status } = useFetch<HomeData>("/api/home", { key: "home" });
const count = (k: string) => data.value?.classes[k] ?? 0;
const shelves = computed(() => [
  { icon: "chart", title: "Популярное за неделю", sub: "Чаще всего открывали в poe2lab", query: { sort: "popular" }, builds: data.value?.shelves.popular ?? [] },
  { icon: "flag", title: "Для старта лиги", sub: "Дёшево, без редких уников, уверенно до карт", query: { tag: "старт лиги" }, builds: data.value?.shelves.start ?? [] },
  { icon: "clock", title: "Новое", sub: "Опубликовано и обновлено за последние дни", query: { sort: "new" }, builds: data.value?.shelves.fresh ?? [] },
]);
const loading = computed(() => status.value === "pending" && !data.value);
const tries = [{ icon: "cold", color: "var(--cold)", text: "холод чары" }, { icon: "skull", text: "миньоны" },
  { icon: "c-monk", text: "удар посох" }, { icon: "lock", text: "SSF" }];
useHead({ title: "poe2lab — билды Path of Exile 2" });
</script>

<template>
  <div class="wrap">
    <section class="hero">
      <h1>Билды Path of Exile 2, <em>посчитанные настоящим движком</em> Path of Building</h1>
      <p>Скиллы, снаряжение, урон и защита — коротко и наглядно. Понравился билд — открой его в poe2lab: прокачка, дерево и советы под твоего персонажа.</p>
      <div class="hero-search">
        <label class="search lg"><Ic name="search" />
          <input v-model="q" type="search" placeholder="Скилл, класс или тег: «холод чары», «миньоны»" aria-label="Поиск билдов" @keydown.enter="find()" />
          <button class="btn btn-primary" type="button" @click="find()">Найти</button></label>
      </div>
      <div class="hero-try"><span>Например:</span>
        <a v-for="x in tries" :key="x.text" class="chip sm" href="#" @click.prevent="find(x.text)"><Ic :name="x.icon" :style="x.color ? { color: x.color } : undefined" />{{ x.text }}</a>
      </div>
      <div class="hero-cta">
        <a class="btn btn-primary btn-lg" href="#app"><Ic name="download" />Скачать poe2lab</a>
        <NuxtLink class="btn btn-ghost btn-lg" to="/catalog"><Ic name="grid4" />Открыть каталог</NuxtLink>
        <small>Приложение для Windows · бесплатно · исходники на GitHub</small>
      </div>
      <div class="how">
        <div class="how-s"><span class="medal">1</span><div><b>Автор собирает билд в poe2lab</b><span>Движок Path of Building считает урон и защиту у него на компьютере.</span></div></div>
        <div class="how-s"><span class="medal">2</span><div><b>Публикует одной кнопкой</b><span>Сюда приходят скиллы, снаряжение, цифры и короткое описание.</span></div></div>
        <div class="how-s"><span class="medal">3</span><div><b>Ты открываешь его в своём poe2lab</b><span>Всё пересчитается, и появятся прокачка, дерево и советы.</span></div></div>
      </div>
    </section>

    <div class="shead"><div><h2><Ic name="person" />Выбери класс</h2><p>Откроется каталог с фильтром по классу</p></div></div>
    <div class="ctiles">
      <NuxtLink v-for="c in CLASSES" :key="c.key" :class="['ctile', `k-${c.key}`]" :to="{ path: '/catalog', query: { cls: c.key } }">
        <span class="cls"><Ic :name="`c-${c.key}`" /></span><b>{{ c.name }}</b><small>{{ c.ascs.join(" · ") }}</small>
        <span class="n"><template v-if="data"><b>{{ count(c.key) }}</b> {{ plural(count(c.key), "билд", "билда", "билдов") }}</template><span v-else class="skel" style="width: 56px" /></span>
      </NuxtLink>
    </div>

    <template v-for="s in shelves" :key="s.title">
      <template v-if="loading || s.builds.length">
      <div class="shead"><div><h2><Ic :name="s.icon" />{{ s.title }}</h2><p>{{ s.sub }}</p></div>
        <NuxtLink class="go" :to="{ path: '/catalog', query: s.query }">Все<Ic name="arrow-r" /></NuxtLink></div>
      <div v-if="loading" class="shelf"><BuildSkel v-for="i in 4" :key="i" /></div>
      <div v-else class="shelf"><BuildTile v-for="b in s.builds" :key="b.id" :b="b" /></div>
      </template>
    </template>

    <template v-if="data?.authors.length">
    <div id="authors" class="shead"><div><h2><Ic name="crown" />Лучшие авторы</h2><p>По средней оценке билдов</p></div></div>
    <div class="agrid">
      <NuxtLink v-for="a in data.authors" :key="a.nick" class="acard" :to="`/a/${a.nick}`">
        <Ava :nick="a.nick" :hue="a.hue" :src="a.avatar ?? undefined" size="l" /><b>{{ a.nick }}</b>
        <span class="clss"><span v-for="k in a.classes" :key="k" :class="['cls', `k-${k}`]"><Ic :name="`c-${k}`" /></span></span>
        <span class="meta"><span><Ic name="star" />{{ fmtRating(a.rating) }}</span><span>{{ a.builds }} {{ plural(a.builds, "билд", "билда", "билдов") }}</span></span>
        <span class="btn btn-sm btn-ghost">Билды автора</span>
      </NuxtLink>
    </div>
    </template>

    <section id="app" class="card ornate appban">
      <div>
        <span class="badge gold">Windows · бесплатно</span>
        <h2>Всё подробное — в приложении poe2lab</h2>
        <p>Сайт показывает основу билда. Приложение пересчитывает его у тебя движком Path of Building и подсказывает, что делать дальше.</p>
        <div class="row">
          <a class="btn btn-primary btn-lg" href="https://github.com/JavelinSx/poe2lab" rel="noopener"><Ic name="download" />Скачать poe2lab</a>
          <a class="btn btn-quiet" href="https://github.com/JavelinSx/poe2lab" rel="noopener"><Ic name="external" />Исходники на GitHub</a>
        </div>
      </div>
      <ul class="appban-f">
        <li><Ic name="flag" /><span><b>Прокачка</b>что брать на каждом уровне</span></li>
        <li><Ic name="tree" /><span><b>Дерево</b>куда расти дальше</span></li>
        <li><Ic name="anvil" /><span><b>Крафт и руны</b>что докрафтить, с ценами</span></li>
        <li><Ic name="compass" /><span><b>Советы</b>в процентах урона и защиты</span></li>
      </ul>
    </section>
  </div>
</template>
