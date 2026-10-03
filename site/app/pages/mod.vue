<script setup lang="ts">
// The site owner's queue of reports: open, solved, bans; a report's details beside the list and what to do with it.
// Every action can be undone from "solved".
const me = useMe();
type Target = "rev" | "build" | "user";
interface Report { id: number; kind: Target; title: string; why: string; n: number; when: string; quote?: string; who?: string; stars?: number; reasons: [string, number][]; note?: string; state: "open" | "solved" }
const reports = ref<Report[]>([
  { id: 1, kind: "rev", title: "Отзыв troll42 на «Шквал бури: молнии с посоха»", why: "оскорбления · «автор вообще играл в игру? билд для…»", n: 5, when: "2 ч",
    who: "troll42", stars: 1, quote: "Автор вообще играл в игру? Билд для [оскорбление], кто это ставит пять звёзд — [оскорбление].",
    reasons: [["Оскорбления", 4], ["Не по теме", 1]], note: "У troll42 уже 2 скрытых отзыва. Аккаунту 4 дня.", state: "open" },
  { id: 2, kind: "build", title: "Билд «ЛУЧШИЙ БИЛД 100КК DPS КУПИ ГАЙД»", why: "реклама и ссылки на продажу · автор goldseller77", n: 8, when: "5 ч", reasons: [["Реклама", 8]], state: "open" },
  { id: 3, kind: "rev", title: "Отзыв Vlad_SSF на «Армия миньонов ведьмы»", why: "«неправда» · жалоба автора билда", n: 1, when: "вчера", reasons: [["Неправда", 1]], state: "open" },
  { id: 4, kind: "user", title: "Аккаунт goldseller77", why: "спам в отзывах · 14 отзывов за час", n: 6, when: "вчера", reasons: [["Спам", 6]], state: "open" },
  { id: 5, kind: "build", title: "Билд «Копьё молнии амазонки»", why: "«украден у другого автора» · 2 жалобы", n: 2, when: "2 дня", reasons: [["Чужой билд", 2]], state: "open" },
]);
const tab = ref<"open" | "solved">("open");
const kind = ref<Target | null>(null);
const list = computed(() => reports.value.filter((r) => r.state === tab.value && (!kind.value || r.kind === kind.value)));
const picked = ref<number>(1);
const cur = computed(() => reports.value.find((r) => r.id === picked.value) ?? list.value[0]);
const toast = useToast();
const reason = ref("Оскорбления — правило 2");
const act = (r: Report, what: string) => {
  r.state = "solved";
  toast(what, { action: { label: "Отменить", run: () => { r.state = "open"; } } });
  picked.value = list.value[0]?.id ?? 0;
};
const KIND_ICON: Record<Target, string> = { rev: "chat", build: "grid4", user: "person" };
useHead({ title: "Жалобы — poe2lab" });
</script>

<template>
  <div class="wrap" style="padding-top: 26px">
    <div v-if="me?.role !== 'owner' && me?.role !== 'mod'" class="empty card" style="margin: 40px auto; max-width: 560px"><Ic name="lock" /><b>Только для модераторов</b></div>
    <template v-else>
      <div class="cab-h">
        <div><h1 style="display: flex; gap: 10px; align-items: center"><Ic name="flag" cls="ic-l" style="color: var(--gold)" />Жалобы</h1><p>Видно только владельцу сайта. Любое действие можно отменить в «Решённых».</p></div>
        <div class="seg soft" role="group" aria-label="Очередь">
          <button :class="{ 'is-on': tab === 'open' }" type="button" @click="tab = 'open'">Открытые<span class="faint">{{ reports.filter((r) => r.state === "open").length }}</span></button>
          <button :class="{ 'is-on': tab === 'solved' }" type="button" @click="tab = 'solved'">Решённые</button></div>
      </div>
      <div class="chips" style="margin-bottom: 14px">
        <button :class="['chip', 'sm', { 'is-on': !kind }]" type="button" @click="kind = null">Все</button>
        <button v-for="[k, n] in [['rev', 'Отзывы'], ['build', 'Билды'], ['user', 'Аккаунты']] as const" :key="k" :class="['chip', 'sm', { 'is-on': kind === k }]" type="button" @click="kind = k">
          <Ic :name="KIND_ICON[k]" />{{ n }}<span class="n">{{ reports.filter((r) => r.kind === k && r.state === tab).length }}</span></button>
      </div>
      <div class="mq">
        <div>
          <div v-for="r in list" :key="r.id" :class="['mrow', { 'is-on': cur?.id === r.id }]" role="button" tabindex="0" @click="picked = r.id">
            <span :class="['mrow-k', r.kind]"><Ic :name="KIND_ICON[r.kind]" /></span>
            <div class="mrow-t"><b>{{ r.title }}</b><span>{{ r.why }}</span></div>
            <span :class="['badge', r.n > 2 ? 'bad' : 'warn']">{{ r.n }} {{ plural(r.n, "жалоба", "жалобы", "жалоб") }}</span><span class="n">{{ r.when }}</span></div>
          <div v-if="!list.length" class="empty card"><Ic name="check" /><b>Очередь пуста</b></div>
        </div>
        <aside v-if="cur" class="panel">
          <div class="panel-h"><h2><Ic :name="KIND_ICON[cur.kind]" />{{ cur.kind === "rev" ? "Отзыв на билд" : cur.kind === "build" ? "Билд" : "Аккаунт" }}</h2></div>
          <div class="panel-b stack" style="gap: 14px">
            <div v-if="cur.quote" class="quote">
              <div class="rv-h" style="margin-bottom: 6px"><Ava :nick="cur.who!" :hue="0" size="xs" /><b style="font-size: 13.5px">{{ cur.who }}</b><Stars :r="cur.stars ?? 0" /><span class="rv-date">3 дня назад</span></div>
              {{ cur.quote }}</div>
            <div><div class="sub-l" style="margin-top: 0">Причины</div>
              <div class="reasons"><div v-for="[w, n] in cur.reasons" :key="w"><Ic name="warn" :style="{ color: n > 2 ? 'var(--bad)' : 'var(--warn)' }" />{{ w }}<span class="n">{{ n }}</span></div></div></div>
            <div v-if="cur.note" class="note"><Ic name="info" /><span>{{ cur.note }}</span></div>
            <div v-if="cur.state === 'open'" class="mact">
              <button v-if="cur.kind === 'rev'" class="btn" type="button" @click="act(cur, 'Отзыв скрыт')"><Ic name="eye-off" />Скрыть отзыв</button>
              <button v-if="cur.kind === 'build'" class="btn" type="button" @click="act(cur, 'Билд скрыт')"><Ic name="grid4" />Скрыть билд</button>
              <button class="btn btn-quiet" type="button" @click="act(cur, 'Жалоба закрыта')"><Ic name="check" />Жалоба зря</button>
              <button class="btn btn-quiet danger" type="button" @click="act(cur, 'Аккаунт заблокирован')"><Ic name="ban" />Заблокировать</button>
            </div>
            <div class="field"><label for="m-note">Причина для автора</label><input id="m-note" v-model="reason" class="input" /></div>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>
