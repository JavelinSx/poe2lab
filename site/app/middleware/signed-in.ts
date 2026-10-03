// The cabinet's pages: without signing in, the sign-in page, and back here after it.
export default defineNuxtRouteMiddleware((to) => {
  if (!useMe().value) return navigateTo({ path: "/login", query: { next: to.fullPath } });
});
