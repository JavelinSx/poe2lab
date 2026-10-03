<script setup lang="ts">
// The cabinet's menu: my builds, notifications, follows, favourites, settings, the app's connection, sign out.
defineProps<{ active: "builds" | "notif" | "subs" | "fav" | "settings" | "connect" }>();
const me = useMe();
</script>

<template>
  <nav class="cab-nav" aria-label="Кабинет">
    <div v-if="me" class="cab-me"><Ava :nick="me.nick" :hue="me.hue" size="l" /><span><b>{{ me.nick }}</b><small>вход через Discord</small></span></div>
    <NuxtLink :class="{ 'is-on': active === 'builds' }" to="/me"><Ic name="grid4" />Мои билды<span class="pill-n">4</span></NuxtLink>
    <NuxtLink :class="{ 'is-on': active === 'notif' }" to="/me/settings"><Ic name="bell" />Уведомления<span v-if="me?.unread" class="pill-n gold">{{ me.unread }}</span></NuxtLink>
    <NuxtLink :class="{ 'is-on': active === 'subs' }" to="/a/MapMama"><Ic name="person" />Подписки</NuxtLink>
    <NuxtLink :class="{ 'is-on': active === 'fav' }" to="/catalog?fav=1"><Ic name="star-o" />Избранное</NuxtLink>
    <hr />
    <NuxtLink :class="{ 'is-on': active === 'settings' }" to="/me/settings#settings"><Ic name="gear" />Настройки</NuxtLink>
    <NuxtLink :class="{ 'is-on': active === 'connect' }" to="/connect"><Ic name="plug" />Подключить poe2lab</NuxtLink>
    <NuxtLink v-if="me && (me.role === 'owner' || me.role === 'mod')" to="/mod"><Ic name="flag" />Жалобы</NuxtLink>
    <NuxtLink to="/login"><Ic name="logout" />Выйти</NuxtLink>
  </nav>
</template>
