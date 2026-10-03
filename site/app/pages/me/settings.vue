<script setup lang="ts">
// Notifications (new reviews, answers, follows, patches, moderation) and the settings the site needs: nick, the
// Discord avatar, about and links, language, which notifications, the sign-in and the connected app.
const me = useMe();
const toast = useToast();
type Kind = "review" | "reply" | "follow" | "patch" | "mod";
const items = ref([
  { kind: "review" as Kind, icon: "star", html: ["IceIsNice", " оценил «Шквал бури» на 5 и оставил отзыв"], when: "3 часа назад", link: "/b/b7#reviews", fresh: true },
  { kind: "review" as Kind, icon: "star", html: ["Kotofey", " оценил «Заряженный посох» на 4"], when: "вчера", link: "/b/b7#reviews", fresh: true },
  { kind: "reply" as Kind, icon: "reply", html: ["MapMama", " ответила на твой отзыв к «Ледяной каскад для первой лиги»"], when: "вчера", fresh: true },
  { kind: "follow" as Kind, icon: "plus", html: ["Inverno", " — новый билд «Ледяной удар + Колокол бури»"], when: "2 дня назад" },
  { kind: "patch" as Kind, icon: "warn", color: "var(--warn)", html: ["", "Вышел патч 0.5.5 — «Ледяной каскад хрономанта» помечен устаревшим. Обнови его в poe2lab."], when: "5 дней назад" },
  { kind: "mod" as Kind, icon: "eye-off", color: "var(--bad)", html: ["troll42", " — модератор скрыл отзыв на «Шквал бури»: оскорбления"], when: "неделю назад" },
]);
const filter = ref<Kind | "all">("all");
const shown = computed(() => items.value.filter((x) => filter.value === "all" || x.kind === filter.value));
const readAll = () => { items.value.forEach((x) => { x.fresh = false; }); if (me.value) me.value = { ...me.value, unread: 0 }; };
const form = reactive({ nick: me.value?.nick ?? "", about: "Монах и холод. Стримлю старт лиги.", twitch: "twitch.tv/frostmonk", youtube: "", lang: "ru",
  reviews: true, replies: true, follows: false });
const app = ref(true);
const asking = ref<"app" | "account" | null>(null);
const nickOk = computed(() => /^[A-Za-zА-Яа-яЁё0-9_-]{3,24}$/.test(form.nick));
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
              <button class="btn btn-sm btn-quiet" type="button" @click="readAll"><Ic name="check" />Всё прочитано</button></div>
            <div class="seg soft" role="group" aria-label="Показать" style="margin-bottom: 12px">
              <button :class="{ 'is-on': filter === 'all' }" type="button" @click="filter = 'all'">Все</button>
              <button :class="{ 'is-on': filter === 'review' }" type="button" @click="filter = 'review'">Отзывы<span class="faint">{{ items.filter((x) => x.kind === "review" && x.fresh).length || "" }}</span></button>
              <button :class="{ 'is-on': filter === 'reply' }" type="button" @click="filter = 'reply'">Ответы</button>
              <button :class="{ 'is-on': filter === 'follow' }" type="button" @click="filter = 'follow'">Подписки</button></div>
            <div class="panel" style="overflow: hidden">
              <div v-for="(n, i) in shown" :key="i" :class="['ntf', { 'is-new': n.fresh }]">
                <span class="ntf-i" :style="n.color ? { color: n.color } : undefined"><Ic :name="n.icon" /></span>
                <span><b v-if="n.html[0]">{{ n.html[0] }}</b>{{ n.html[1] }}<small>{{ n.when }}<template v-if="n.link"> · <NuxtLink :to="n.link">ответить</NuxtLink></template></small></span></div>
              <div v-if="!shown.length" class="empty" style="padding: 24px"><Ic name="bell" /><b>Здесь пусто</b></div>
              <div class="notif-f"><button class="btn btn-sm btn-ghost" type="button">Показать старые</button></div>
            </div>
          </div>

          <div id="settings">
            <div class="cab-h"><div><h1>Настройки</h1><p>Только то, что нужно сайту</p></div></div>
            <div class="panel fset">
              <div class="field"><label for="st-nick">Ник</label>
                <div class="inwrap"><input id="st-nick" v-model.trim="form.nick" class="input" maxlength="24" />
                  <span v-if="nickOk" class="count-in" style="color: var(--good); display: inline-flex; gap: 4px; align-items: center"><Ic name="check" cls="ic-s" />свободен</span>
                  <span v-else class="count-in" style="color: var(--bad)">не подходит</span></div>
                <p class="hint">3–24 знака: буквы, цифры, _ и -. Виден на билдах и отзывах.</p></div>
              <div class="field"><label>Аватар</label>
                <div class="row"><Ava :nick="form.nick || '?'" :hue="me?.hue" size="l" /><span class="hint" style="flex: 1">Берём из Discord. Поменял там — нажми «Обновить».</span>
                  <button class="btn btn-sm" type="button" @click="toast('Аватар обновлён из Discord')"><Ic name="refresh" />Обновить</button></div></div>
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
                <div class="device" style="margin-top: 0"><Ic name="chat" style="color: #8f97f7" /><span style="flex: 1"><b>Discord · {{ form.nick }}</b><span>Берём только ник и аватар. Почту не берём.</span></span></div>
                <div v-if="app" class="device" style="margin-top: 6px"><Ic name="monitor" /><span style="flex: 1"><b>poe2lab на этом компьютере</b><span>подключено 12 сентября · может публиковать билды</span></span>
                  <button class="btn btn-sm btn-quiet danger" type="button" @click="asking = 'app'">Отключить</button></div>
                <p v-else class="hint" style="margin-top: 6px">Приложение не подключено — <NuxtLink to="/connect">подключить</NuxtLink>.</p></div>
              <div class="row" style="justify-content: space-between; padding-top: 6px; border-top: 1px solid var(--line)">
                <button class="btn btn-primary" type="button" :disabled="!nickOk" @click="toast('Настройки сохранены')">Сохранить</button>
                <button class="btn btn-sm btn-quiet danger" type="button" @click="asking = 'account'"><Ic name="trash" />Удалить аккаунт…</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
    <ConfirmDialog v-if="asking === 'app'" title="Отключить poe2lab?" text="Приложение больше не сможет публиковать и обновлять твои билды. Подключить снова — по коду из приложения."
      yes="Отключить" icon="plug" @yes="app = false; asking = null; toast('Приложение отключено')" @no="asking = null" />
    <ConfirmDialog v-if="asking === 'account'" title="Удалить аккаунт?" text="Удалятся твои билды, отзывы и подписки. Это навсегда."
      yes="Удалить аккаунт" danger icon="trash" @yes="asking = null; me = null; navigateTo('/')" @no="asking = null" />
  </div>
</template>
