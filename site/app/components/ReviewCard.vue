<script setup lang="ts">
// One review: who wrote it (their character), stars, criteria, the text, "helpful" (one vote, a toggle, not on one's
// own), the build's author's answer - which the author writes or changes right here; on an author's page also which
// build it is about.
import { className } from "~~/shared/catalog";
import { CRIT, type BuildCard, type ReviewItem } from "~~/shared/api";
const props = defineProps<{ r: ReviewItem; author: { nick: string; hue: number; avatar?: string | null }; on?: BuildCard; canReply?: boolean }>();
const me = useMe();
const toast = useToast();
const needLogin = useNeedLogin();

const voted = ref(!!props.r.voted);
const helpful = ref(props.r.helpful);
const busy = ref(false);
async function vote() {
  if (!me.value) return needLogin("Отметить отзыв полезным");
  busy.value = true;
  try {
    const res = await $fetch<{ voted: boolean; helpful: number }>(`/api/reviews/${props.r.id}/helpful`, { method: "POST" });
    voted.value = res.voted; helpful.value = res.helpful;
  } catch (e) { toast(apiError(e), { bad: true }); } finally { busy.value = false; }
}
const crit = computed(() => CRIT.filter((c) => props.r.crit[c.key]).map((c) => [c.name.split(" ")[0], props.r.crit[c.key]!] as const));

// the author's answer: written, changed or taken off (an empty answer)
const reply = ref(props.r.reply);
const writing = ref(false);
const draft = ref("");
const open = () => { draft.value = reply.value?.text ?? ""; writing.value = true; };
async function send() {
  busy.value = true;
  try {
    await $fetch(`/api/reviews/${props.r.id}/reply`, { method: "POST", body: { text: draft.value } });
    reply.value = draft.value.trim() ? { text: draft.value.trim(), at: Math.floor(Date.now() / 1000) } : null;
    writing.value = false;
    toast(reply.value ? "Ответ опубликован" : "Ответ убран");
  } catch (e) { toast(apiError(e), { bad: true }); } finally { busy.value = false; }
}
</script>

<template>
  <article class="rv">
    <Ava :nick="r.nick" :hue="r.hue" :src="r.avatar ?? undefined" />
    <div style="min-width: 0">
      <div class="rv-h"><b>{{ r.nick }}</b>
        <span v-if="r.cls" class="rv-char"><span :class="['cls', `k-${r.cls}`]"><Ic :name="`c-${r.cls}`" /></span>{{ className(r.cls) }}<template v-if="r.level"> · {{ r.level }} ур.</template></span>
        <Stars :r="r.stars" /><span class="rv-date">{{ fmtWhen(r.at) }}</span><span v-if="r.own" class="badge">твой отзыв</span></div>
      <NuxtLink v-if="on" class="rv-on" :to="`/b/${on.id}`"><BuildArt :b="on" cls="gi gi-s" />к билду «{{ on.title }}»</NuxtLink>
      <div v-if="crit.length" class="rv-crit"><span v-for="[k, v] in crit" :key="k">{{ k }} <b>{{ v }}</b></span></div>
      <p class="rv-t">{{ r.text }}</p>
      <div class="rv-f">
        <button v-if="!r.own" :class="['btn', 'btn-quiet', { 'is-on': voted }]" type="button" :aria-pressed="voted" :disabled="busy" @click="vote"><Ic name="thumb" />Полезно · {{ helpful }}</button>
        <span v-else class="faint" style="font-size: 12.5px"><Ic name="thumb" /> полезно · {{ helpful }}</span>
        <button v-if="canReply && !writing" class="btn btn-quiet" type="button" @click="open"><Ic name="reply" />{{ reply ? "Изменить ответ" : "Ответить" }}</button>
      </div>
      <div v-if="writing" class="rv-reply">
        <textarea v-model="draft" class="textarea" rows="3" maxlength="1000" placeholder="Ответ увидят все под этим отзывом" aria-label="Ответ автора" />
        <div class="row" style="margin-top: 8px; gap: 8px"><button class="btn btn-sm btn-primary" type="button" :disabled="busy || (!draft.trim() && !reply)" @click="send">
          {{ draft.trim() ? "Опубликовать ответ" : "Убрать ответ" }}</button><button class="btn btn-sm btn-quiet" type="button" @click="writing = false">Отмена</button></div>
      </div>
      <div v-else-if="reply" class="rv-reply">
        <div class="rv-h"><Ava :nick="author.nick" :hue="author.hue" :src="author.avatar ?? undefined" size="xs" /><b>{{ author.nick }}</b><span class="badge gold">автор</span><span class="rv-date">{{ fmtWhen(reply.at) }}</span></div>
        <p class="rv-t">{{ reply.text }}</p>
      </div>
    </div>
  </article>
</template>
