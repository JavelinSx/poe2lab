<script setup lang="ts">
// The phone's bottom bar: home, catalog, favourites, the cabinet with the new notifications.
const route = useRoute();
const me = useMe();
const on = (p: string) => (p === "/" ? route.path === "/" : route.path.startsWith(p)) ? "is-on" : "";
</script>

<template>
  <nav class="mnav" aria-label="Навигация">
    <NuxtLink :class="on('/')" to="/"><Ic name="home" />Главная</NuxtLink>
    <NuxtLink :class="on('/catalog')" to="/catalog"><Ic name="grid4" />Каталог</NuxtLink>
    <NuxtLink :class="on('/fav')" to="/catalog?fav=1"><Ic name="star-o" />Избранное</NuxtLink>
    <NuxtLink :class="on('/me')" to="/me"><Ic name="person" />Кабинет<span v-if="me && me.unread" class="bell-n">{{ me.unread }}</span></NuxtLink>
  </nav>
</template>
