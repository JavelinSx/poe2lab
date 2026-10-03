<script setup lang="ts">
// A build's page: its head, the numbers in short, the author's word with the game's pieces in it, skills and gems,
// gear on the doll, the author, the reviews; the rest is in the app ("Открыть в poe2lab").
import { BUILDS, className } from "~~/mock/builds";
import { PAGES } from "~~/mock/page";
import { MY_BUILDS } from "~~/mock/mine";

const route = useRoute();
const b = computed(() => BUILDS.find((x) => x.id === route.params.id));
const p = computed(() => PAGES[String(route.params.id)] || PAGES.b1!);
// a build its author took off the site: its page says so and leads to the author's other builds
const hidden = computed(() => MY_BUILDS.some((m) => m.id === route.params.id && m.state === "hidden"));
useHead(() => ({ title: b.value ? `${b.value.title} — poe2lab` : "Билд не найден — poe2lab" }));

// resistances: capped, short of the cap (by how much), immune
const CAP = 75;
const resists = computed(() => ([["fire", "fire", "Огонь"], ["cold", "cold", "Холод"], ["light", "bolt", "Молния"], ["chaos", "chaos", "Хаос"]] as const)
  .map(([k, icon, name]) => {
    const v = p.value.numbers.res[k];
    return { k, icon, name, v, state: v === "imm" ? "imm" : v >= CAP ? "ok" : "low" };
  }));

// the reviews: sorted, the form (one review per account), "helpful" as a toggle
const sorts = [["helpful", "Полезные"], ["new", "Новые"], ["high", "Высокие"], ["low", "Низкие"]] as const;
const rsort = ref<string>("helpful");
const reviews = computed(() => {
  const list = [...p.value.reviews.items];
  if (rsort.value === "helpful") list.sort((a, c) => c.helpful - a.helpful);
  if (rsort.value === "high") list.sort((a, c) => c.stars - a.stars);
  if (rsort.value === "low") list.sort((a, c) => a.stars - c.stars);
  return list;
});
const stars = ref(4);
const crit = reactive<Record<string, number>>({ "Урон": 5, "Живучесть": 3, "Бюджет": 0, "Лёгкость игры": 0 });
const text = ref("");
const me = useMe();
const toast = useToast();
const copyCode = async () => { try { await navigator.clipboard.writeText("<код PoB>"); toast("Код PoB скопирован"); } catch { toast("Не удалось скопировать"); } };
// "Открыть в poe2lab": the app's link; if the page is still seen 2 s later, the app is not there - offer it
const notOpened = ref(false);
function openInApp() {
  const shown = Date.now();
  window.location.href = `poe2lab://build/${route.params.id}`;
  setTimeout(() => { if (document.visibilityState === "visible" && Date.now() - shown < 3000) notOpened.value = true; }, 2000);
}
</script>

<template>
  <div v-if="!b" class="wrap" style="padding: 40px 0; max-width: 620px">
    <StatePanel code="404" title="Такой страницы нет" text="Возможно, ссылка с ошибкой или билд удалили.">
      <div class="row"><NuxtLink class="btn btn-primary" to="/catalog"><Ic name="grid4" />В каталог</NuxtLink><NuxtLink class="btn btn-quiet" to="/">На главную</NuxtLink></div>
    </StatePanel>
  </div>
  <div v-else-if="hidden" class="wrap" style="padding: 40px 0; max-width: 620px">
    <StatePanel icon="eye-off" title="Автор снял билд с публикации" text="Он может вернуть его позже. У автора есть другие билды.">
      <div class="row"><NuxtLink class="btn btn-primary" :to="`/a/${b.author}`"><Ic name="person" />Билды автора</NuxtLink><NuxtLink class="btn btn-quiet" to="/catalog">В каталог</NuxtLink></div>
    </StatePanel>
  </div>
  <div v-else class="wrap">
    <nav class="crumbs" aria-label="Путь"><NuxtLink to="/">Главная</NuxtLink><Ic name="chev-r" /><NuxtLink to="/catalog">Каталог</NuxtLink><Ic name="chev-r" />
      <NuxtLink :to="{ path: '/catalog', query: { cls: b.cls } }">{{ className(b.cls) }}</NuxtLink><Ic name="chev-r" /><span>{{ b.asc }}</span></nav>

    <!-- 1. the head -->
    <header class="bhead">
      <div class="bhead-art"><span class="gframe"><BuildArt :b="b" /></span></div>
      <div style="min-width: 0">
        <h1>{{ b.title }}</h1>
        <div class="bhead-who">
          <NuxtLink class="author" :to="`/a/${b.author}`"><Ava :nick="b.author" :hue="b.hue" size="s" />{{ b.author }}</NuxtLink>
          <ClsLine :cls="b.cls" :asc="b.asc" />
          <span><BuildArt :b="b" cls="gi gi-s" />{{ b.skill }}</span>
        </div>
        <div class="bhead-meta">
          <span class="rate"><Stars :r="b.rating" /><b>{{ fmtRating(b.rating) }}</b><a href="#reviews">{{ b.reviews }} {{ plural(b.reviews, "отзыв", "отзыва", "отзывов") }}</a></span>
          <span><Ic name="eye" />{{ fmtInt(p.views) }} просмотров</span>
          <span><Ic name="monitor" />{{ fmtInt(b.opens) }} открыли в poe2lab</span>
          <span><PatchBadge :patch="b.patch" :old="b.old" />обновлено {{ new Date(b.updated).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) }}</span>
        </div>
        <div class="bhead-tags"><span v-for="(t, i) in [...b.tags, b.weapon]" :key="t" :class="['tag', { gold: i === 0 }]">{{ t }}</span></div>
      </div>
      <div class="bact">
        <button class="btn btn-primary btn-lg" type="button" @click="openInApp"><Ic name="monitor" />Открыть в poe2lab</button>
        <div class="bact-row">
          <button class="btn" type="button" @click="copyCode"><Ic name="copy" />Код PoB</button>
          <button class="btn" type="button"><Ic name="star-o" />В избранное</button>
          <span class="hov"><button class="icon-btn" type="button" aria-label="Поделиться"><Ic name="share" /></button>
            <span class="pop below" style="left: auto; right: 0; transform: none"><span class="menu" style="display: block">
              <button type="button"><Ic name="link" />Скопировать ссылку</button>
              <button type="button"><Ic name="chat" />Ссылка с превью для Discord</button>
              <button type="button" @click="copyCode"><Ic name="copy" />Код PoB</button>
            </span></span></span>
          <button class="icon-btn" type="button" aria-label="Пожаловаться"><Ic name="flag" /></button>
        </div>
        <small>Нет poe2lab? <NuxtLink to="/#app">Скачать для Windows</NuxtLink></small>
      </div>
    </header>

    <!-- 2. the numbers in short -->
    <section class="nums" aria-label="Цифры билда">
      <div class="stat"><div class="stat-l"><Ic name="sword" />DPS</div><div class="stat-n">{{ fmtInt(p.numbers.dps) }}</div>
        <div class="stat-s"><BuildArt :b="b" cls="gi gi-s" />{{ p.numbers.dpsNote }}</div></div>
      <div class="stat"><div class="stat-l"><Ic name="shield" :style="{ color: 'var(--mana)' }" />{{ p.numbers.es ? "Здоровье + энергощит" : "Здоровье" }}</div>
        <div class="stat-n">{{ fmtInt(p.numbers.life) }}<template v-if="p.numbers.es"><span class="plus">+</span>{{ fmtInt(p.numbers.es) }}</template></div>
        <div class="stat-s">{{ p.numbers.poolNote }}</div></div>
      <div class="stat"><div class="stat-l"><Ic name="scales" />Сопротивления</div>
        <div class="res4">
          <div v-for="r in resists" :key="r.k" :class="['res', r.k, r.state]" :title="r.state === 'low' ? `${r.name}: ${r.v}%, до капа не хватает ${CAP - (r.v as number)}` : undefined">
            <Ic :name="r.icon" /><b>{{ r.state === "imm" ? "иммун." : `${r.v}%` }}</b>
            <small v-if="r.state === 'low'"><Ic name="warn" />−{{ CAP - (r.v as number) }} до капа</small>
            <small v-else-if="r.state === 'ok'"><Ic name="check" />в капе</small>
            <small v-else>к хаосу</small>
          </div>
        </div></div>
      <div class="stat"><div class="stat-l"><Ic name="run" />Главная защита</div><div class="stat-n">{{ fmtInt(p.numbers.defence.value) }}</div>
        <div class="stat-s">{{ p.numbers.defence.kind }}<template v-if="p.numbers.defence.extra"><span class="faint">·</span>{{ p.numbers.defence.extra }}</template></div></div>
    </section>
    <div class="nums-f">
      <span class="calc hov" tabindex="0"><span class="calc-i"><Ic name="seal" /></span>Посчитано в <b>poe2lab</b> у автора<span class="sep">·</span>Path of Building<span class="sep">·</span>патч {{ b.patch }}
        <span class="pop below" style="left: 0; transform: none"><span class="tipcard" style="display: block">
          <span class="tc-h term" style="display: block"><b>Откуда эти цифры</b><small>посчитано {{ new Date(b.updated).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) }}</small></span>
          <span class="tc-b" style="text-align: left"><span>Автор открыл билд в poe2lab, и движок Path of Building посчитал урон и защиту — как в самом PoB. Сайт показывает эти цифры как есть и ничего не пересчитывает.</span>
            <span class="tc-sep" /><span>Открой билд в своём poe2lab — всё посчитается заново, у тебя на компьютере.</span></span></span></span>
      </span>
      <span>Прокачка, дерево и советы — в приложении</span>
    </div>

    <div class="bbody">
      <div class="bcol">
        <!-- 3. the author's word -->
        <section class="panel" aria-labelledby="h-desc">
          <div class="panel-h"><h2 id="h-desc"><Ic name="quote" />От автора</h2><span class="x">наведи на иконку — подсказка</span></div>
          <div class="panel-b prose"><RichText :text="p.description" :cards="p.cards" /></div>
        </section>

        <!-- 4. skills and gems -->
        <section class="panel" aria-labelledby="h-skills">
          <div class="panel-h"><h2 id="h-skills"><Ic name="gem" />Скиллы и камни</h2><span class="x">{{ 1 + p.groups.reduce((n, g) => n + g.links.length, 0) }} связок</span></div>
          <div class="panel-b" style="display: flex; flex-direction: column; gap: 6px">
            <div class="link-main">
              <div class="lm-h"><span class="gframe"><img class="gi" :src="gameArt(p.main.img)" alt="" /></span>
                <div class="lm-t"><b>{{ p.main.name }}</b><span><span class="role role-core"><Ic name="target" />главный скилл</span><span class="badge lvl gold">{{ p.main.level }}</span>
                  <span :class="['dt', p.main.dmg]"><Ic :name="p.main.dmg === 'light' ? 'bolt' : p.main.dmg" />{{ p.main.dmgName }}</span><span>{{ p.main.tags }}</span></span></div>
              </div>
              <div class="lm-sup">
                <span v-for="s in p.main.supports" :key="s.name" class="gem lg hov" tabindex="0"><img :src="gameArt(s.img!)" alt="" /><span class="gem-n">{{ s.name }}</span>
                  <span v-if="s.card" class="pop below"><TipCard :card="s.card" /></span></span>
              </div>
              <div v-if="p.main.note" class="lm-note"><Ava :nick="b.author" :hue="b.hue" size="s" /><div><b>{{ b.author }}:</b> <RichText :text="p.main.note" :cards="p.cards" inline /></div></div>
            </div>
            <template v-for="g in p.groups" :key="g.title">
              <div class="lg-k">{{ g.title }}</div>
              <div v-for="l in g.links" :key="l.name" class="lg">
                <span class="gframe"><img v-if="l.img" class="gi" :src="gameArt(l.img)" alt="" /><span v-else :class="['gi', 'gph', l.ph]"><Ic :name="l.ph === 'light' ? 'bolt' : l.ph!" /></span></span>
                <div class="lg-t">{{ l.name }}<span v-if="l.dmg" :class="['dt', l.dmg]"><Ic :name="l.dmg === 'light' ? 'bolt' : l.dmg" />{{ l.dmgName }}</span><span v-if="l.badge" class="badge lvl">{{ l.badge }}</span></div>
                <div v-if="l.supports.length" class="lg-s"><span v-for="s in l.supports" :key="s.name" class="sup hov" tabindex="0"><img :src="gameArt(s.img!)" alt="" />{{ s.name }}</span></div>
              </div>
            </template>
          </div>
        </section>
      </div>

      <div class="bcol">
        <!-- 5. gear -->
        <section class="panel" aria-labelledby="h-gear">
          <div class="panel-h"><h2 id="h-gear"><Ic name="helm" />Снаряжение</h2><span class="x">{{ p.gearSummary }}</span></div>
          <div class="panel-b gear-wrap">
            <div class="doll doll-site">
              <div v-for="it in p.gear" :key="it.pos" :class="['slot', `s-${it.pos}`, it.img ? `r-${it.rarity}` : 'empty', { hov: it.card }]" :tabindex="it.card ? 0 : undefined">
                <template v-if="it.img"><img :src="gameArt(it.img)" :alt="it.label" />
                  <span v-if="it.runes?.length" class="socks"><img v-for="(r, i) in it.runes" :key="i" :src="gameArt(r)" alt="" /></span></template>
                <span v-else>{{ it.label }}</span>
                <span v-if="it.card" :class="['pop', it.tip ?? 'below']"><TipCard :card="it.card" /></span>
              </div>
            </div>
            <div class="gear-note doll-note"><Ic name="info" />Наведи на вещь — её моды и руны</div>
            <div class="slotlist">
              <details v-for="it in p.gear.filter((x) => x.card)" :key="it.pos" class="sl"><summary>
                <span :class="['sl-art', `r-${it.rarity}`]"><img :src="gameArt(it.img!)" alt="" /></span>
                <span class="sl-t"><small>{{ it.slot }}</small><b :class="it.rarity">{{ it.card!.name }}</b></span>
                <span class="sl-runes"><img v-for="(r, i) in it.runes || []" :key="i" :src="gameArt(r)" alt="" /></span><Ic name="chev" /></summary>
                <div class="sl-b"><span class="kv">{{ it.card!.sub }}</span><span class="tc-sep" /><span v-for="m in it.card!.mods" :key="m">{{ m }}</span>
                  <template v-if="it.card!.runes"><span class="tc-sep" /><span v-for="r in it.card!.runes" :key="r.text" class="tc-rune"><img :src="gameArt(r.img)" alt="" />{{ r.text }}</span></template></div>
              </details>
            </div>
          </div>
        </section>

        <section class="panel" aria-label="Автор">
          <div class="panel-b" style="padding-top: 16px">
            <div class="aplate" style="padding: 0; border: 0; background: none">
              <Ava :nick="b.author" :hue="b.hue" size="l" />
              <div class="aplate-t"><b>{{ b.author }}</b><span>5 билдов · ★ {{ fmtRating(b.rating) }} · {{ p.followers }} подписчиков</span></div>
              <button class="btn btn-sm btn-ghost follow" type="button"><Ic name="plus" />Подписаться</button>
            </div>
            <div class="links" style="margin-top: 12px">
              <a v-for="l in p.links" :key="l.label" :href="l.href"><Ic :name="l.icon" />{{ l.label }}</a>
              <NuxtLink :to="`/a/${b.author}`">Все билды автора<Ic name="arrow-r" /></NuxtLink>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 6. reviews -->
    <section id="reviews" aria-labelledby="h-rev">
      <div class="shead"><div><h2 id="h-rev"><Ic name="chat" />Отзывы<span class="faint" style="font-weight: 500">{{ p.reviews.n }}</span></h2></div>
        <div class="seg soft" role="group" aria-label="Сортировка отзывов">
          <button v-for="[k, name] in sorts" :key="k" :class="{ 'is-on': rsort === k }" type="button" @click="rsort = k">{{ name }}</button></div></div>
      <div class="panel rsum">
        <div class="rsum-big"><b>{{ fmtRating(p.reviews.avg) }}</b><Stars :r="p.reviews.avg" cls="l" /><small>{{ p.reviews.n }} {{ plural(p.reviews.n, "отзыв", "отзыва", "отзывов") }}</small></div>
        <div class="dist">
          <div v-for="[s, n] in p.reviews.dist" :key="s" class="dist-r"><span>{{ s }} <Ic name="star" /></span><span class="bar"><i :style="{ '--v': `${Math.round((n / p.reviews.n) * 100)}%` }" /></span><span>{{ n }}</span></div>
        </div>
        <div class="crit">
          <div v-for="[icon, name, v] in p.reviews.crit" :key="name" class="crit-r"><Ic :name="icon" /><span>{{ name }}</span><span class="bar"><i :style="{ '--v': `${(v / 5) * 100}%` }" /></span><b>{{ fmtRating(v) }}</b></div>
        </div>
      </div>

      <div class="rv-grid" style="margin-top: 14px">
        <div class="rv-list">
          <ReviewCard v-for="r in reviews" :key="r.nick" :r="r" :author="{ nick: b.author, hue: b.hue }" />
          <div v-if="p.reviews.n > reviews.length" class="more" style="margin-top: 8px"><button class="btn btn-ghost" type="button">Показать ещё {{ p.reviews.n - reviews.length }} {{ plural(p.reviews.n - reviews.length, "отзыв", "отзыва", "отзывов") }}</button></div>
        </div>

        <aside class="panel" aria-labelledby="h-form">
          <div class="panel-h"><h2 id="h-form"><Ic name="edit" />Твой отзыв</h2></div>
          <div v-if="!me" class="rform" style="padding-top: 2px"><NuxtLink class="btn btn-primary" to="/login"><Ic name="login" />Войти через Discord</NuxtLink></div>
          <div v-else-if="me.nick === b.author" class="rform hint" style="padding-top: 2px">Это твой билд: отвечай под отзывами.</div>
          <div v-else class="rform" style="padding-top: 2px">
            <div class="field"><label>Оценка</label>
              <div class="starpick" role="radiogroup" aria-label="Оценка"><button v-for="i in 5" :key="i" :class="{ on: i <= stars }" type="button" :aria-label="String(i)" @click="stars = i"><Ic name="star" /></button></div></div>
            <div class="field"><label>По критериям <span style="text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--faint)">— по желанию</span></label>
              <div class="crit-pick">
                <template v-for="(v, k) in crit" :key="k"><span>{{ k }}</span>
                  <div class="starpick sm"><button v-for="i in 5" :key="i" :class="{ on: i <= v }" type="button" :aria-label="String(i)" @click="crit[k] = crit[k] === i ? 0 : i"><Ic name="star" /></button></div></template>
              </div></div>
            <div class="field"><label for="rv-cls">Твой персонаж</label>
              <div class="row2"><select id="rv-cls" class="sel"><option v-for="c in ['Монах', 'Воин', 'Следопыт', 'Ведьма', 'Волшебница', 'Наёмник', 'Охотница', 'Друид']" :key="c">{{ c }}</option></select>
                <input class="input" type="number" value="72" aria-label="Уровень" /></div></div>
            <div class="field"><label for="rv-t">Отзыв</label>
              <textarea id="rv-t" v-model="text" class="textarea" rows="4" maxlength="1000" placeholder="Как играется, что было сложно, где умираешь" />
              <div class="count"><span>Один отзыв на аккаунт, можно править</span><span><b>{{ text.length }}</b> / 1 000</span></div></div>
            <button class="btn btn-primary" type="button" :disabled="!text.trim()">Опубликовать отзыв</button>
          </div>
        </aside>
      </div>
    </section>

    <!-- 7. the rest is in the app -->
    <section id="open" class="card ornate inapp">
      <div class="inapp-ic"><span><Ic name="flag" /></span><span><Ic name="tree" /></span><span><Ic name="anvil" /></span></div>
      <div><h3>Прокачка, дерево, разбор и советы — в poe2lab</h3><p>Приложение откроет этот билд, пересчитает его у тебя и покажет, что делать на каждом уровне.</p></div>
      <div class="inapp-a"><button class="btn btn-primary btn-lg" type="button" @click="openInApp"><Ic name="monitor" />Открыть в poe2lab</button><small>Нет приложения? <NuxtLink to="/#app">Скачать</NuxtLink></small></div>
    </section>

    <ConfirmDialog v-if="notOpened" title="poe2lab не открылся" text="Похоже, приложение не установлено. Скачай его — билд откроется по этой же кнопке."
      yes="Скачать poe2lab" no="Закрыть" @yes="navigateTo('https://github.com/JavelinSx/poe2lab', { external: true })" @no="notOpened = false" />
  </div>
</template>
