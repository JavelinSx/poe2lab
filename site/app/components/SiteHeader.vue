<script setup lang="ts">
// The site's head: logo, sections, search ("/" puts the cursor there), language, the one who came in.
const route = useRoute();
const router = useRouter();
const me = useMe();
const q = ref("");
const input = ref<HTMLInputElement | null>(null);
const on = (section: string) => (route.path.startsWith(`/${section}`) ? "is-on" : "");
const search = () => router.push({ path: "/catalog", query: q.value.trim() ? { q: q.value.trim() } : {} });
function slash(e: KeyboardEvent) {
  const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA)$|true/.test(e.target.tagName + e.target.contentEditable);
  if (e.key === "/" && !typing) { e.preventDefault(); input.value?.focus(); }
}
onMounted(() => document.addEventListener("keydown", slash));
onBeforeUnmount(() => document.removeEventListener("keydown", slash));
</script>

<template>
  <header class="sh">
    <div class="wrap sh-in">
      <NuxtLink class="logo" to="/">poe2<span>lab</span></NuxtLink>
      <nav class="sh-nav" aria-label="Разделы">
        <NuxtLink :class="on('catalog')" to="/catalog"><Ic name="grid4" />Каталог</NuxtLink>
        <NuxtLink :class="on('a')" to="/a/MapMama"><Ic name="crown" />Авторы</NuxtLink>
        <NuxtLink to="/#app"><Ic name="download" />Приложение</NuxtLink>
      </nav>
      <label class="search sh-search"><Ic name="search" />
        <input ref="input" v-model="q" type="search" placeholder="Билд, скилл или тег" aria-label="Поиск билдов" @keydown.enter="search" />
        <span class="kbd">/</span></label>
      <div class="sh-end">
        <NuxtLink class="icon-btn only-phone" to="/catalog" aria-label="Поиск"><Ic name="search" cls="ic-l" /></NuxtLink>
        <div class="lang"><button class="is-on" type="button">RU</button><button type="button">EN</button></div>
        <template v-if="me">
          <div class="bell"><NuxtLink class="icon-btn" to="/me/settings" :aria-label="`Уведомления: ${me.unread} новых`"><Ic name="bell" /></NuxtLink><span v-if="me.unread" class="bell-n">{{ me.unread }}</span></div>
          <NuxtLink class="sh-me" to="/me"><Ava :nick="me.nick" :hue="me.hue" size="s" /><span class="nick">{{ me.nick }}</span><Ic name="chev" /></NuxtLink>
        </template>
        <NuxtLink v-else class="btn btn-sm btn-ghost" to="/login"><Ic name="login" />Войти</NuxtLink>
      </div>
    </div>
  </header>
</template>
