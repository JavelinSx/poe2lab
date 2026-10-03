<script setup lang="ts">
// Editing a build on the site: the title, the tags, the card's cover and tint, the description with the game's
// pieces (the editor and the search panel beside it). Skills, gear and numbers come only from the app. Leaving with
// changes not saved asks in the page. The build comes from /api/builds/:id (the author sees it taken off too); saving
// sends the changes and the cards of the pieces added from the search (PATCH).
import { TAGS, type Dmg } from "~~/shared/catalog";
import { LIMITS, TOKEN, visibleLength, type Card } from "~~/shared/package";
import type { BuildPageData } from "~~/shared/api";
import type { GameThing } from "~~/mock/game";

definePageMeta({ middleware: "signed-in" });
const route = useRoute();
const router = useRouter();
const toast = useToast();
const id = String(route.params.id);
const { data, error, refresh } = useFetch<BuildPageData>(`/api/builds/${id}`, { key: `edit-${id}` });
const b = computed(() => data.value?.card);
const page = computed(() => data.value?.page);

const form = reactive({ title: "", tags: [] as string[], cover: "", tint: "phys" as Dmg, description: "" });
const saved = ref("");
watch(data, (d) => {
  if (!d || saved.value) return;
  Object.assign(form, { title: d.card.title, tags: [...d.card.tags], cover: d.card.cover, tint: d.card.dmg, description: d.page.description });
  saved.value = JSON.stringify(form);
}, { immediate: true });
const dirty = computed(() => !!saved.value && JSON.stringify(form) !== saved.value);

// the pieces the text can hold: the build's own cards, and the ones found in the search
const cards = computed<Record<string, Card>>(() => ({ ...cardsOf(), ...(page.value?.cards ?? {}) }));
const editor = ref<{ insertToken: (k: string) => void } | null>(null);
const TITLE_MAX = LIMITS.title, TAGS_MAX = LIMITS.tags;
const descLength = computed(() => visibleLength(form.description, cards.value));
const canSave = computed(() => dirty.value && form.title.trim() && form.title.length <= TITLE_MAX && descLength.value <= LIMITS.description && !saving.value);
const toggleTag = (t: string) => {
  if (form.tags.includes(t)) form.tags = form.tags.filter((x) => x !== t);
  else if (form.tags.length < TAGS_MAX) form.tags.push(t);
  else toast(`Не больше ${TAGS_MAX} тегов`, { bad: true });
};
// the covers: the build's own pictures (its skill, its gear)
const covers = computed(() => [...new Set([b.value?.icon, b.value?.cover, page.value?.main.img, ...(page.value?.gear ?? []).map((g) => g.img)]
  .filter((x): x is string => !!x))].slice(0, 8));
const tints: Dmg[] = ["phys", "fire", "cold", "light", "chaos"];
const preview = computed(() => ({ ...b.value!, title: form.title || "Без названия", tags: form.tags, cover: form.cover, dmg: form.tint }));

const saving = ref(false);
async function save() {
  saving.value = true;
  try {
    const own = page.value!.cards;
    const added = Object.fromEntries([...form.description.matchAll(TOKEN)].map((m) => m[1]!).filter((k) => !own[k] && cards.value[k]).map((k) => [k, cards.value[k]!]));
    await $fetch(`/api/builds/${id}`, { method: "PATCH", body: { ...form, title: form.title.trim(), cards: Object.keys(added).length ? added : undefined } });
    data.value = { ...data.value!, card: { ...data.value!.card, title: form.title.trim(), tags: [...form.tags], cover: form.cover, dmg: form.tint },
      page: { ...page.value!, description: form.description, cards: { ...own, ...added } } };
    saved.value = JSON.stringify(form);
    toast("Сохранено — изменения уже на сайте");
    return true;
  } catch (e) { toast(apiError(e), { bad: true }); return false; } finally { saving.value = false; }
}

// the from-app summary: what the app published and when
const gems = computed(() => (page.value ? 1 + page.value.main.supports.length + page.value.groups.reduce((n, g) => n + g.links.reduce((m, l) => m + 1 + l.supports.length, 0), 0) : 0));
const links = computed(() => (page.value ? 1 + page.value.groups.reduce((n, g) => n + g.links.length, 0) : 0));
const items = computed(() => page.value?.gear.filter((g) => g.img).length ?? 0);
const runes = computed(() => page.value?.gear.reduce((n, g) => n + (g.runes?.length ?? 0), 0) ?? 0);

// the search panel beside the editor
const q = ref("");
const kinds = ref<GameThing["kind"][] | null>(null);
const KINDS: [GameThing["kind"] | null, string][] = [[null, "Всё"], ["skill", "Скиллы"], ["support", "Поддержки"], ["unique", "Уники"], ["pass", "Пассивки"], ["term", "Термины"]];
const rows = computed(() => lookup(q.value, kinds.value, 8));
const panel = ref(true);

// leaving with changes: "save / don't save" in the page
const leaving = ref<string | null>(null);
onBeforeRouteLeave((to) => {
  if (dirty.value && leaving.value === null) { leaving.value = to.fullPath; return false; }
});
async function leave(saveFirst: boolean) {
  if (saveFirst && !await save()) { leaving.value = null; return; }
  if (!saveFirst) saved.value = JSON.stringify(form);
  const to = leaving.value!;
  leaving.value = null;
  router.push(to);
}

// taking it off and deleting
const asking = ref<"hide" | "delete" | null>(null);
async function setState(state: "published" | "hidden" | "removed") {
  asking.value = null;
  try {
    await $fetch(`/api/builds/${id}/state`, { method: "POST", body: { state } });
    if (state === "removed") { saved.value = JSON.stringify(form); toast("Билд удалён"); return router.push("/me"); }
    data.value = { ...data.value!, card: { ...data.value!.card, status: state } };
    toast(state === "hidden" ? "Билд снят с публикации" : "Билд снова на сайте", state === "hidden" ? { action: { label: "Отменить", run: () => setState("published") } } : {});
  } catch (e) { toast(apiError(e), { bad: true }); }
}
useHead(() => ({ title: `Правка: ${b.value?.title ?? "билд"} — poe2lab` }));
</script>

<template>
  <div class="wrap">
    <div class="cab">
      <CabNav active="builds" />
      <section style="min-width: 0">
        <NuxtLink class="btn btn-sm btn-quiet" to="/me" style="margin: -4px 0 10px -10px"><Ic name="arrow-l" />Мои билды</NuxtLink>
        <StatePanel v-if="apiStatus(error) === 404" code="404" title="Такого билда нет" text="Возможно, его уже удалили.">
          <NuxtLink class="btn btn-primary" to="/me"><Ic name="grid4" />Мои билды</NuxtLink></StatePanel>
        <LoadError v-else-if="error" :error="error" @retry="refresh()" />
        <div v-else-if="!b || !page" class="panel" style="padding: 18px; display: flex; flex-direction: column; gap: 12px">
          <span v-for="i in 4" :key="i" class="skel" style="height: 40px" /></div>
        <StatePanel v-else-if="!data!.mine" icon="lock" title="Это не твой билд" text="Править можно только свои билды.">
          <NuxtLink class="btn btn-primary" :to="`/b/${b.id}`"><Ic name="eye" />Открыть билд</NuxtLink></StatePanel>
        <template v-else>
        <div class="cab-h">
          <div><h1>{{ form.title || "Без названия" }}</h1>
            <p style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap"><span v-if="b.status === 'hidden'" class="badge"><Ic name="eye-off" />снят с публикации</span>
              <span v-else class="badge good"><Ic name="check" />на сайте</span><PatchBadge :patch="b.patch" :old="b.old" />изменения видны сразу после сохранения</p></div>
          <div class="row"><NuxtLink class="btn btn-quiet" :to="`/b/${b.id}`"><Ic name="eye" />Посмотреть</NuxtLink>
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
              <div><b>Скиллы, снаряжение и цифры — из poe2lab</b><span>Здесь их не правят: на сайте всегда то, что посчитал Path of Building. Последний раз — {{ fmtDate(daySec(b.updated)) }}.</span>
                <div class="ro-list"><span><Ic name="scroll" />код PoB</span><span><Ic name="gem" />{{ links }} {{ plural(links, "связка", "связки", "связок") }} · {{ gems }} {{ plural(gems, "камень", "камня", "камней") }}</span>
                  <span><Ic name="helm" />{{ items }} {{ plural(items, "вещь", "вещи", "вещей") }}<template v-if="runes"> · {{ runes }} {{ plural(runes, "руна", "руны", "рун") }}</template></span>
                  <span><Ic name="sword" />DPS {{ fmtInt(b.dps) }}</span><span><Ic name="shield" />{{ fmtInt(b.life) }}<template v-if="b.es"> + {{ fmtInt(b.es) }}</template></span><PatchBadge :patch="b.patch" :old="b.old" /></div></div>
              <span class="hov"><button class="btn btn-ghost" type="button"><Ic name="refresh" />Обновить из poe2lab</button>
                <span class="pop below" style="left: auto; right: 0; transform: none"><span class="tipcard" style="display: block; width: 300px"><span class="tc-b" style="text-align: left">
                  <span>Откроет билд в poe2lab на этом компьютере. Пересчитай и нажми «Опубликовать» — сайт обновит данные, отзывы и ссылка останутся.</span></span></span></span></span>
            </div>

            <div class="panel fset" style="flex-direction: row; flex-wrap: wrap; align-items: center; gap: 10px">
              <div style="flex: 1; min-width: 240px"><b style="font-size: 14px">Снять или удалить</b><p class="hint" style="margin-top: 3px">Снятый билд виден только тебе, отзывы сохраняются. Удаление — навсегда.</p></div>
              <button v-if="b.status === 'hidden'" class="btn" type="button" @click="setState('published')"><Ic name="upload" />Вернуть на сайт</button>
              <button v-else class="btn" type="button" @click="asking = 'hide'"><Ic name="eye-off" />Снять с публикации</button>
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
        </template>
      </section>
    </div>

    <ConfirmDialog v-if="leaving !== null" title="Сохранить изменения?" text="Ты поправил билд, но не сохранил. Без сохранения правки пропадут."
      yes="Сохранить" no="Не сохранять" icon="edit" @yes="leave(true)" @no="leave(false)" />
    <ConfirmDialog v-if="asking === 'hide'" :title="`Снять «${form.title}» с публикации?`" text="Билд пропадёт из каталога и поиска. Отзывы и оценки сохранятся — вернёшь одной кнопкой."
      yes="Снять" icon="eye-off" @yes="setState('hidden')" @no="asking = null" />
    <ConfirmDialog v-if="asking === 'delete'" :title="`Удалить «${form.title}»?`" text="Билд, его отзывы и оценки удалятся насовсем."
      yes="Удалить" danger icon="trash" @yes="setState('removed')" @no="asking = null" />
  </div>
</template>
