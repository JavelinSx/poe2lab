<script setup lang="ts">
// Notifications (new reviews, answers, new builds of the authors followed, patches, moderation) and the settings the
// site needs: nick, the Discord avatar, about and links, language, which notifications, the sign-in and the connected
// apps. Notifications: /api/notifications; settings: /api/me/settings, saved with PATCH /api/me.
import { nickOk } from "~~/shared/catalog";
import type { Notice, Settings } from "~~/shared/api";

definePageMeta({ middleware: "signed-in" });
const me = useMe();
const toast = useToast();

// notifications, 30 at a time ("Показать старые" asks for the ones before the last)
type Kind = Notice["kind"];
const items = ref<Notice[]>([]);
const more = ref(false);
const nloading = ref(true);
async function loadNotices(older = false) {
  nloading.value = true;
  try {
    const before = older ? items.value[items.value.length - 1]?.at : undefined;
    const got = await $fetch<Notice[]>("/api/notifications", { query: { before } });
    items.value = older ? [...items.value, ...got] : got;
    more.value = got.length === 30;
  } catch (e) { toast(apiError(e), { bad: true }); } finally { nloading.value = false; }
}
onMounted(() => loadNotices());
const ICONS: Record<Kind, [string, string?]> = { review: ["star"], reply: ["reply"], follow: ["plus"], patch: ["warn", "var(--warn)"], mod: ["eye-off", "var(--bad)"] };
const filter = ref<Kind | "all">("all");
const shown = computed(() => items.value.filter((x) => filter.value === "all" || x.kind === filter.value));
async function readAll() {
  try {
    await $fetch("/api/notifications/read", { method: "POST" });
    items.value = items.value.map((x) => ({ ...x, fresh: false }));
    if (me.value) me.value = { ...me.value, unread: 0 };
  } catch (e) { toast(apiError(e), { bad: true }); }
}

// the settings
const { data: st, refresh } = useFetch<Settings>("/api/me/settings", { key: "settings" });
const form = reactive({ nick: "", about: "", twitch: "", youtube: "", lang: "ru" as "ru" | "en", reviews: true, replies: true, follows: true });
watch(st, (v) => {
  if (!v) return;
  Object.assign(form, { nick: v.nick, about: v.bio, twitch: v.links.find((l) => l.kind === "twitch")?.url ?? "", youtube: v.links.find((l) => l.kind === "youtube")?.url ?? "",
    lang: v.lang, ...v.notify });
}, { immediate: true });
const nickValid = computed(() => nickOk(form.nick));
const saving = ref(false);
async function save() {
  saving.value = true;
  try {
    await $fetch("/api/me", { method: "PATCH", body: { nick: form.nick, bio: form.about, lang: form.lang,
      links: [{ kind: "twitch", url: form.twitch }, { kind: "youtube", url: form.youtube }],
      notify: { reviews: form.reviews, replies: form.replies, follows: form.follows } } });
    await Promise.all([loadMe(), refresh(), loadNotices()]);
    toast("Настройки сохранены");
  } catch (e) { toast(apiError(e), { bad: true }); } finally { saving.value = false; }
}

// the apps and the account
const asking = ref<{ app: Settings["apps"][number] } | "account" | null>(null);
async function dropApp(app: Settings["apps"][number]) {
  asking.value = null;
  try { await $fetch(`/api/me/apps/${app.id}`, { method: "DELETE" }); await refresh(); toast("Приложение отключено"); }
  catch (e) { toast(apiError(e), { bad: true }); }
}
async function dropAccount() {
  asking.value = null;
  try { await $fetch("/api/me", { method: "DELETE" }); me.value = null; toast("Аккаунт удалён"); await navigateTo("/"); }
  catch (e) { toast(apiError(e), { bad: true }); }
}
useHead({ title: "Уведомления и настройки — poe2lab" });
</script>

<template>
  <div class="wrap">
    <div class="cab">
      <CabNav active="notif" />
      <section style="min-width: 0">
        <div class="acc">
          <div>
            <div class="cab-h"><div><h1>Уведомления</h1><p>Новые отзывы на твои билды и ответы тебе</p></div>
              <button class="btn btn-sm btn-quiet" type="button" :disabled="!items.some((x) => x.fresh)" @click="readAll"><Ic name="check" />Всё прочитано</button></div>
            <div class="seg soft" role="group" aria-label="Показать" style="margin-bottom: 12px">
              <button :class="{ 'is-on': filter === 'all' }" type="button" @click="filter = 'all'">Все</button>
              <button :class="{ 'is-on': filter === 'review' }" type="button" @click="filter = 'review'">Отзывы<span class="faint">{{ items.filter((x) => x.kind === "review" && x.fresh).length || "" }}</span></button>
              <button :class="{ 'is-on': filter === 'reply' }" type="button" @click="filter = 'reply'">Ответы</button>
              <button :class="{ 'is-on': filter === 'follow' }" type="button" @click="filter = 'follow'">Новые билды</button></div>
            <div class="panel" style="overflow: hidden">
              <div v-for="n in shown" :key="n.id" :class="['ntf', { 'is-new': n.fresh }]">
                <span class="ntf-i" :style="ICONS[n.kind][1] ? { color: ICONS[n.kind][1] } : undefined"><Ic :name="ICONS[n.kind][0]" /></span>
                <span>
                  <template v-if="n.kind === 'review'">Новый отзыв от <b>{{ n.actor ?? "удалённого аккаунта" }}</b> к «{{ n.build?.title }}»<template v-if="n.stars"> — ★ {{ n.stars }}</template></template>
                  <template v-else-if="n.kind === 'reply'">Ответ от <b>{{ n.actor ?? "автора" }}</b> на твой отзыв к «{{ n.build?.title }}»</template>
                  <template v-else-if="n.kind === 'follow'">Новый билд <b>{{ n.actor }}</b>: «{{ n.build?.title }}»</template>
                  <template v-else-if="n.kind === 'patch'">{{ n.text || `Вышел новый патч — «${n.build?.title}» помечен устаревшим. Обнови его в poe2lab.` }}</template>
                  <template v-else>{{ n.text }}</template>
                  <small>{{ fmtWhen(n.at) }}<template v-if="n.build"> · <NuxtLink :to="`/b/${n.build.id}${n.kind === 'follow' ? '' : '#reviews'}`">{{ n.kind === "review" ? "ответить" : "открыть" }}</NuxtLink></template></small></span></div>
              <div v-if="nloading && !items.length" style="padding: 16px; display: flex; flex-direction: column; gap: 10px"><span v-for="i in 3" :key="i" class="skel" style="height: 30px" /></div>
              <div v-else-if="!shown.length" class="empty" style="padding: 24px"><Ic name="bell" /><b>Здесь пусто</b></div>
              <div v-if="more" class="notif-f"><button class="btn btn-sm btn-ghost" type="button" :disabled="nloading" @click="loadNotices(true)">Показать старые</button></div>
            </div>
          </div>

          <div id="settings">
            <div class="cab-h"><div><h1>Настройки</h1><p>Только то, что нужно сайту</p></div></div>
            <div class="panel fset">
              <div class="field"><label for="st-nick">Ник</label>
                <div class="inwrap"><input id="st-nick" v-model.trim="form.nick" class="input" maxlength="24" />
                  <span v-if="nickValid" class="count-in" style="color: var(--good); display: inline-flex; gap: 4px; align-items: center"><Ic name="check" cls="ic-s" />подходит</span>
                  <span v-else class="count-in" style="color: var(--bad)">не подходит</span></div>
                <p class="hint">3–24 знака: буквы, цифры, _ и -. Виден на билдах и отзывах.</p></div>
              <div class="field"><label>Аватар</label>
                <div class="row"><Ava :nick="form.nick || '?'" :hue="me?.hue" :src="me?.avatar ?? undefined" size="l" /><span class="hint" style="flex: 1">Берём из Discord при входе. Без Discord — буквы ника.</span></div></div>
              <div class="field"><label>О себе и ссылки</label>
                <textarea v-model="form.about" class="textarea" rows="2" maxlength="300" aria-label="О себе" />
                <div class="row2" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px"><input v-model="form.twitch" class="input" placeholder="twitch.tv/…" aria-label="Twitch" />
                  <input v-model="form.youtube" class="input" placeholder="youtube.com/…" aria-label="YouTube" /></div></div>
              <div class="field"><label>Язык сайта</label><div class="seg soft">
                <button :class="{ 'is-on': form.lang === 'ru' }" type="button" @click="form.lang = 'ru'">Русский</button>
                <button :class="{ 'is-on': form.lang === 'en' }" type="button" @click="form.lang = 'en'">English</button></div></div>
              <div class="field"><label>Присылать уведомления</label>
                <div class="toggles">
                  <label><span>Новые отзывы на мои билды</span><span class="switch"><input v-model="form.reviews" type="checkbox" /><span /></span></label>
                  <label><span>Ответы на мои отзывы</span><span class="switch"><input v-model="form.replies" type="checkbox" /><span /></span></label>
                  <label><span>Новые билды авторов, на которых подписан</span><span class="switch"><input v-model="form.follows" type="checkbox" /><span /></span></label>
                </div></div>
              <div class="field"><label>Вход и приложение</label>
                <div class="device" style="margin-top: 0"><Ic name="chat" style="color: #8f97f7" /><span style="flex: 1"><b>{{ st?.discord ? `Discord · ${st.nick}` : "Вход для разработки" }}</b><span>Берём только ник и аватар. Почту не берём.</span></span></div>
                <div v-for="app in st?.apps ?? []" :key="app.id" class="device" style="margin-top: 6px"><Ic name="monitor" /><span style="flex: 1"><b>{{ app.name }}</b>
                  <span>подключено {{ fmtDate(app.created) }}<template v-if="app.used"> · публиковало {{ fmtWhen(app.used) }}</template></span></span>
                  <button class="btn btn-sm btn-quiet danger" type="button" @click="asking = { app }">Отключить</button></div>
                <p v-if="st && !st.apps.length" class="hint" style="margin-top: 6px">Приложение не подключено — <NuxtLink to="/connect">подключить</NuxtLink>.</p></div>
              <div class="row" style="justify-content: space-between; padding-top: 6px; border-top: 1px solid var(--line)">
                <button class="btn btn-primary" type="button" :disabled="!nickValid || saving || !st" @click="save">Сохранить</button>
                <button class="btn btn-sm btn-quiet danger" type="button" @click="asking = 'account'"><Ic name="trash" />Удалить аккаунт…</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
    <ConfirmDialog v-if="asking && asking !== 'account'" :title="`Отключить «${asking.app.name}»?`" text="Приложение больше не сможет публиковать и обновлять твои билды. Подключить снова — по коду из приложения."
      yes="Отключить" icon="plug" @yes="dropApp((asking as { app: Settings['apps'][number] }).app)" @no="asking = null" />
    <ConfirmDialog v-if="asking === 'account'" title="Удалить аккаунт?" text="Удалятся твои билды, отзывы и подписки. Это навсегда."
      yes="Удалить аккаунт" danger icon="trash" @yes="dropAccount" @no="asking = null" />
  </div>
</template>
