<script setup lang="ts">
// Editing a build on the site: the title, the tags, the card's cover and tint, the description with the game's
// pieces (the editor and the search panel beside it). Skills, gear and numbers come only from the app. Leaving with
// changes not saved asks in the page.
import { BUILDS, TAGS, type Dmg } from "~~/mock/builds";
import { MY_BUILDS } from "~~/mock/mine";
import type { GameThing } from "~~/mock/game";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const mine = MY_BUILDS.find((b) => b.id === route.params.id) ?? MY_BUILDS[0]!;
const card = BUILDS.find((b) => b.id === mine.id) ?? BUILDS[6]!;
const form = reactive({ title: mine.title, tags: [...mine.tags], cover: mine.cover, tint: card.dmg as Dmg, description: mine.description });
const saved = ref(JSON.stringify(form));
const dirty = computed(() => JSON.stringify(form) !== saved.value);
const cards = cardsOf();
const editor = ref<{ insertToken: (k: string) => void } | null>(null);
const TITLE_MAX = 60, TAGS_MAX = 5;
const descLength = computed(() => form.description.replace(/\[\[([a-z]+:[^[\]\n]+)\]\]/g, (_, k) => cards[k]?.name ?? "").length);
const canSave = computed(() => dirty.value && form.title.trim() && form.title.length <= TITLE_MAX && descLength.value <= 1500);
const toggleTag = (t: string) => {
  if (form.tags.includes(t)) form.tags = form.tags.filter((x) => x !== t);
  else if (form.tags.length < TAGS_MAX) form.tags.push(t);
  else toast(`Не больше ${TAGS_MAX} тегов`, { bad: true });
};
const covers = [mine.icon, "i-staff2", "i-body", "i-gloves", "asc-invoker"];
const tints: Dmg[] = ["phys", "fire", "cold", "light", "chaos"];
const preview = computed(() => ({ ...card, title: form.title || "Без названия", tags: form.tags, cover: form.cover, dmg: form.tint }));
function save() { saved.value = JSON.stringify(form); toast("Сохранено — изменения уже на сайте"); }

// the search panel beside the editor
const q = ref("атака удар посох");
const kinds = ref<GameThing["kind"][] | null>(["skill"]);
const KINDS: [GameThing["kind"] | null, string][] = [[null, "Всё"], ["skill", "Скиллы"], ["support", "Поддержки"], ["unique", "Уники"], ["pass", "Пассивки"], ["term", "Термины"]];
const rows = computed(() => lookup(q.value, kinds.value, 8));
const panel = ref(true);

// leaving with changes: "save / don't save" in the page
const leaving = ref<string | null>(null);
onBeforeRouteLeave((to) => {
  if (dirty.value && leaving.value === null) { leaving.value = to.fullPath; return false; }
});
function leave(saveFirst: boolean) {
  if (saveFirst) save(); else saved.value = JSON.stringify(form);
  const to = leaving.value!;
  leaving.value = null;
  router.push(to);
}
const asking = ref<"hide" | "delete" | null>(null);
useHead({ title: `Правка: ${mine.title} — poe2lab` });
</script>

<template>
  <div class="wrap">
    <div class="cab">
      <CabNav active="builds" />
      <section style="min-width: 0">
        <NuxtLink class="btn btn-sm btn-quiet" to="/me" style="margin: -4px 0 10px -10px"><Ic name="arrow-l" />Мои билды</NuxtLink>
        <div class="cab-h">
          <div><h1>{{ form.title || "Без названия" }}</h1>
            <p style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap"><span class="badge good"><Ic name="check" />на сайте</span><PatchBadge :patch="mine.patch" :old="mine.old" />изменения видны сразу после сохранения</p></div>
          <div class="row"><NuxtLink class="btn btn-quiet" :to="`/b/${mine.id}`"><Ic name="eye" />Посмотреть</NuxtLink>
            <button class="btn btn-primary" type="button" :disabled="!canSave" @click="save"><Ic name="check" />Сохранить</button></div>
        </div>

        <div class="edit">
          <div class="stack">
            <div class="panel fset">
              <div class="field"><label for="ed-name">Название</label>
                <div class="inwrap"><input id="ed-name" v-model="form.title" class="input" :maxlength="TITLE_MAX" style="padding-right: 64px" /><span class="count-in">{{ form.title.length }} / {{ TITLE_MAX }}</span></div></div>
              <div class="field"><label>Теги <span style="text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--faint)">— до {{ TAGS_MAX }}, по ним ищут</span></label>
                <div class="chips"><button v-for="t in TAGS" :key="t.name" :class="['chip', { 'is-on': form.tags.includes(t.name) }]" type="button" @click="toggleTag(t.name)"><Ic :name="t.icon" />{{ t.name }}</button></div>
                <p class="hint">Класс, скилл, тип урона и оружие подставляются сами — из билда.</p></div>
              <div class="cover-grid" style="display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 18px; align-items: start">
                <div class="field"><label>Обложка карточки</label>
                  <div class="covers"><button v-for="c in covers" :key="c" :class="['cover-o', { 'is-on': form.cover === c }]" type="button" :aria-label="c" @click="form.cover = c"><img :src="gameArt(c)" alt="" /></button></div>
                  <p class="hint">Картинка из билда — бледно, справа в карточке.</p>
                  <label style="margin-top: 8px">Цвет подложки</label>
                  <div class="tints"><button v-for="t in tints" :key="t" :class="['tint', t, { 'is-on': form.tint === t }]" type="button" :aria-label="t" @click="form.tint = t" /></div>
                </div>
                <div><div class="lbl" style="font-size: 11.5px; color: var(--faint); margin-bottom: 6px">так увидят в каталоге</div><BuildTile :b="preview" /></div>
              </div>
            </div>

            <div class="panel fset">
              <div class="field"><label>Описание</label><DescEditor ref="editor" v-model="form.description" :cards="cards" /></div>
            </div>

            <div class="from-app">
              <Ic name="seal" />
              <div><b>Скиллы, снаряжение и цифры — из poe2lab</b><span>Здесь их не правят: на сайте всегда то, что посчитал Path of Building. Последний раз — 12 сентября, 18:40.</span>
                <div class="ro-list"><span><Ic name="scroll" />код PoB</span><span><Ic name="gem" />9 связок · 31 камень</span><span><Ic name="helm" />14 вещей · 8 рун</span>
                  <span><Ic name="sword" />DPS {{ fmtInt(card.dps) }}</span><span><Ic name="shield" />{{ fmtInt(card.life) }} + {{ fmtInt(card.es) }}</span><PatchBadge :patch="mine.patch" :old="mine.old" /></div></div>
              <span class="hov"><button class="btn btn-ghost" type="button"><Ic name="refresh" />Обновить из poe2lab</button>
                <span class="pop below" style="left: auto; right: 0; transform: none"><span class="tipcard" style="display: block; width: 300px"><span class="tc-b" style="text-align: left">
                  <span>Откроет билд в poe2lab на этом компьютере. Пересчитай и нажми «Опубликовать» — сайт обновит данные, отзывы и ссылка останутся.</span></span></span></span></span>
            </div>

            <div class="panel fset" style="flex-direction: row; flex-wrap: wrap; align-items: center; gap: 10px">
              <div style="flex: 1; min-width: 240px"><b style="font-size: 14px">Снять или удалить</b><p class="hint" style="margin-top: 3px">Снятый билд виден только тебе, отзывы сохраняются. Удаление — навсегда.</p></div>
              <button class="btn" type="button" @click="asking = 'hide'"><Ic name="eye-off" />Снять с публикации</button>
              <button class="btn btn-quiet danger" type="button" @click="asking = 'delete'"><Ic name="trash" />Удалить билд</button>
            </div>
          </div>

          <aside v-if="panel" class="cpanel no-phone">
            <div class="cpanel-h"><Ic name="search" />Найти и вставить<span class="spacer" /><button class="icon-btn sm" type="button" aria-label="Свернуть" @click="panel = false"><Ic name="x" cls="ic-s" /></button></div>
            <p>Камень, вещь, пассивка или термин. Перетащи в текст или нажми — встанет туда, где курсор.</p>
            <label class="search"><Ic name="search" /><input v-model="q" type="search" aria-label="Поиск" placeholder="Название или теги: атака удар посох" /></label>
            <div class="chips"><button v-for="[k, n] in KINDS" :key="n" :class="['chip', { 'is-on': k === null ? !kinds : kinds?.includes(k) }]" type="button" @click="kinds = k ? [k] : null">{{ n }}</button></div>
            <LookupRow v-for="g in rows" :key="g.key" :g="g" :q="q" grip @click="editor?.insertToken(g.key)" />
            <p v-if="q.trim() && !rows.length" class="hint">Ничего не нашлось</p>
            <p class="hint">Ищет по-русски и по-английски, по названию и тегам.</p>
          </aside>
          <button v-else class="btn btn-ghost no-phone" type="button" style="align-self: start" @click="panel = true"><Ic name="search" />Найти и вставить</button>
        </div>
      </section>
    </div>

    <ConfirmDialog v-if="leaving !== null" title="Сохранить изменения?" text="Ты поправил билд, но не сохранил. Без сохранения правки пропадут."
      yes="Сохранить" no="Не сохранять" icon="edit" @yes="leave(true)" @no="leave(false)" />
    <ConfirmDialog v-if="asking === 'hide'" :title="`Снять «${form.title}» с публикации?`" text="Билд пропадёт из каталога и поиска. Отзывы и оценки сохранятся — вернёшь одной кнопкой."
      yes="Снять" icon="eye-off" @yes="asking = null; toast('Билд снят с публикации', { action: { label: 'Отменить', run: () => {} } })" @no="asking = null" />
    <ConfirmDialog v-if="asking === 'delete'" :title="`Удалить «${form.title}»?`" text="Билд, его отзывы и оценки удалятся насовсем."
      yes="Удалить" danger icon="trash" @yes="asking = null; saved = JSON.stringify(form); router.push('/me')" @no="asking = null" />
  </div>
</template>
