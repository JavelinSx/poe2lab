<script setup lang="ts">
// The author's cabinet: the numbers in all, each build with its state and numbers; edit, open, update from the app,
// take off the site (undone from the toast), delete (asked in the page). The builds come from /api/me/builds.
import type { MyBuildCard } from "~~/shared/api";

definePageMeta({ middleware: "signed-in" });
const { data, error, refresh, status } = useFetch<MyBuildCard[]>("/api/me/builds", { key: "my-builds", default: () => [] });
const builds = computed(() => data.value);
const toast = useToast();
const menu = ref<string | null>(null);
const asking = ref<MyBuildCard | null>(null);
const total = (k: "views" | "opens" | "reviews" | "newReviews") => builds.value.reduce((s, b) => s + (b[k] ?? 0), 0);
const rated = computed(() => builds.value.filter((b) => b.reviews));
const avg = computed(() => rated.value.reduce((s, b) => s + b.rating * b.reviews, 0) / Math.max(1, rated.value.reduce((s, b) => s + b.reviews, 0)));
const thousands = (n: number) => (n >= 10000 ? `${fmtRating(n / 1000)} тыс.` : fmtInt(n));
const icon = (b: MyBuildCard) => b.icon || b.cover;

async function setState(b: MyBuildCard, state: "published" | "hidden" | "removed") {
  await $fetch(`/api/builds/${b.id}/state`, { method: "POST", body: { state } });
  if (state === "removed") data.value = data.value.filter((x) => x.id !== b.id);
  else data.value = data.value.map((x) => (x.id === b.id ? { ...x, status: state } : x));
}
async function hide(b: MyBuildCard) {
  menu.value = null;
  try {
    await setState(b, "hidden");
    toast("Билд снят с публикации", { action: { label: "Отменить", run: () => restore(b) } });
  } catch (e) { toast(apiError(e), { bad: true }); }
}
async function restore(b: MyBuildCard) {
  try { await setState(b, "published"); toast("Билд снова на сайте"); } catch (e) { toast(apiError(e), { bad: true }); }
}
async function remove(b: MyBuildCard) {
  asking.value = null;
  try { await setState(b, "removed"); toast("Билд удалён"); } catch (e) { toast(apiError(e), { bad: true }); }
}
async function copyLink(b: MyBuildCard) {
  menu.value = null;
  try { await navigator.clipboard.writeText(`${location.origin}/b/${b.id}`); toast("Ссылка скопирована"); } catch { toast("Не удалось скопировать", { bad: true }); }
}
const closeMenu = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest(".mb-a")) menu.value = null; };
onMounted(() => document.addEventListener("click", closeMenu));
onBeforeUnmount(() => document.removeEventListener("click", closeMenu));
useHead({ title: "Мои билды — poe2lab" });
</script>

<template>
  <div class="wrap">
    <div class="cab">
      <CabNav active="builds" :builds="builds.length" />
      <section style="min-width: 0">
        <div class="cab-h">
          <div><h1>Мои билды</h1><p>Публикуются из приложения. Здесь можно поправить название, теги, обложку и описание.</p></div>
          <span class="hov"><button class="btn btn-ghost" type="button"><Ic name="upload" />Как опубликовать новый</button>
            <span class="pop below" style="left: auto; right: 0; transform: none"><span class="tipcard" style="display: block; width: 300px">
              <span class="tc-h term" style="display: block"><b>Публикация — из poe2lab</b></span>
              <span class="tc-b" style="text-align: left"><span>Открой билд в приложении и нажми «Опубликовать» в меню билда. Скиллы, снаряжение и цифры уйдут сюда сами.</span></span></span></span></span>
        </div>

        <div class="kpis">
          <div class="stat"><div class="stat-l"><Ic name="eye" />Просмотры</div><div class="stat-n">{{ thousands(total("views")) }}</div><div class="stat-s">за всё время</div></div>
          <div class="stat"><div class="stat-l"><Ic name="monitor" />Открыли в poe2lab</div><div class="stat-n">{{ fmtInt(total("opens")) }}</div><div class="stat-s">за всё время</div></div>
          <div class="stat"><div class="stat-l"><Ic name="star" />Средняя оценка</div><div class="stat-n">{{ rated.length ? fmtRating(avg) : "—" }}</div><div class="stat-s">{{ total("reviews") }} {{ plural(total("reviews"), "отзыв", "отзыва", "отзывов") }}</div></div>
          <div class="stat"><div class="stat-l"><Ic name="chat" />Новые отзывы</div><div class="stat-n">{{ total("newReviews") }}</div><div class="stat-s"><NuxtLink v-if="total('newReviews')" to="/me/settings">ответить</NuxtLink><template v-else>все прочитаны</template></div></div>
        </div>

        <LoadError v-if="error" :error="error" @retry="refresh()" />
        <div v-else-if="status === 'pending' && !builds.length" class="panel" style="padding: 18px; display: flex; flex-direction: column; gap: 12px">
          <span v-for="i in 3" :key="i" class="skel" style="height: 44px" /></div>
        <div v-else-if="!builds.length" class="empty card"><Ic name="upload" /><b>Пока нет опубликованных билдов</b>
          <span>Открой билд в poe2lab и нажми «Опубликовать» — он появится здесь.</span><NuxtLink class="btn btn-primary" to="/#app"><Ic name="download" />Скачать poe2lab</NuxtLink></div>
        <template v-else>
          <div class="mb-head"><span /><span>Билд</span><span>Просмотры</span><span>Оценка</span><span>В poe2lab</span><span>Отзывы</span><span /></div>
          <div v-for="b in builds" :key="b.id" :class="['mb', { 'is-off': b.status === 'hidden' }]">
            <span class="gframe"><img v-if="icon(b)" class="gi" :src="gameArt(icon(b))" alt="" /><BuildArt v-else :b="b" /></span>
            <div class="mb-t"><b>{{ b.title }}</b>
              <span v-if="b.status === 'published'"><span class="badge good"><Ic name="check" />на сайте</span><PatchBadge :patch="b.patch" :old="b.old" />
                <template v-if="b.old">обнови в poe2lab</template><template v-else>обновлён {{ fmtDate(daySec(b.updated)) }}</template></span>
              <span v-else><span class="badge"><Ic name="eye-off" />снят с публикации</span>виден только тебе</span></div>
            <div class="mb-n"><b>{{ fmtInt(b.views ?? 0) }}</b><small>просмотров</small></div>
            <div class="mb-n"><b>{{ b.reviews ? fmtRating(b.rating) : "—" }}</b><small>{{ b.reviews ? `${b.reviews} ${plural(b.reviews, "отзыв", "отзыва", "отзывов")}` : "нет отзывов" }}</small></div>
            <div class="mb-n"><b>{{ fmtInt(b.opens) }}</b><small>открыли</small></div>
            <div class="mb-n"><b>{{ b.reviews }}</b><span v-if="b.newReviews" class="badge gold">+{{ b.newReviews }} {{ plural(b.newReviews, "новый", "новых", "новых") }}</span><small v-else>новых нет</small></div>
            <div v-if="b.status === 'published'" class="mb-a">
              <NuxtLink class="btn btn-sm" :to="`/me/b/${b.id}`"><Ic name="edit" />Править</NuxtLink>
              <NuxtLink class="icon-btn" :to="`/b/${b.id}`" aria-label="Открыть на сайте"><Ic name="external" /></NuxtLink>
              <span :class="['hov', { 'is-open': menu === b.id }]"><button class="icon-btn" type="button" aria-label="Ещё" @click="menu = menu === b.id ? null : b.id"><Ic name="dots" /></button>
                <span v-if="menu === b.id" class="pop below" style="left: auto; right: 0; transform: none"><span class="menu" style="display: block">
                  <button type="button" @click="menu = null; toast('Обновить можно из poe2lab: «Опубликовать» в меню билда')"><Ic name="refresh" />Обновить из poe2lab</button>
                  <button type="button" @click="copyLink(b)"><Ic name="link" />Скопировать ссылку</button>
                  <hr />
                  <button type="button" @click="hide(b)"><Ic name="eye-off" />Снять с публикации</button>
                  <button type="button" class="danger" @click="menu = null; asking = b"><Ic name="trash" />Удалить…</button>
                </span></span></span>
            </div>
            <div v-else class="mb-a">
              <button class="btn btn-sm btn-ghost" type="button" @click="restore(b)"><Ic name="upload" />Вернуть</button>
              <NuxtLink class="icon-btn" :to="`/me/b/${b.id}`" aria-label="Править"><Ic name="edit" /></NuxtLink>
              <button class="icon-btn" type="button" aria-label="Удалить" @click="asking = b"><Ic name="trash" /></button></div>
          </div>
        </template>
        <p class="hint" style="margin-top: 14px; display: flex; gap: 6px; align-items: center"><Ic name="seal" style="color: var(--guide)" />Цифры, скиллы и снаряжение меняются только из приложения — так на сайте всегда то, что посчитал PoB.</p>
      </section>
    </div>
    <ConfirmDialog v-if="asking" :title="`Удалить «${asking.title}»?`" text="Билд, его отзывы и оценки удалятся насовсем. Чтобы просто убрать его из каталога — сними с публикации."
      yes="Удалить" danger icon="trash" @yes="remove(asking!)" @no="asking = null" />
  </div>
</template>
