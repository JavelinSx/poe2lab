// The one signed in (Discord; in development a nick), or null. Loaded once when the site opens (plugins/me.client.ts).
import type { Me } from "~~/shared/api";

export const useMe = () => useState<Me | null>("me", () => null);

export async function loadMe() {
  const me = useMe();
  try { me.value = (await $fetch<Me | null>("/api/me")) ?? null; } catch { me.value = null; }
}

export async function signOut() {
  try { await $fetch("/api/logout", { method: "POST" }); } catch { /* the cookie goes anyway on its expiry */ }
  useMe().value = null;
  await navigateTo("/");
}
