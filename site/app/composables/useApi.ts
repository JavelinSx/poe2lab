// The API's errors for the page: its own words (the API answers in Russian), or what happened in plain words.
interface Failed { statusCode?: number; status?: number; response?: unknown; data?: { statusMessage?: string; message?: string; data?: Record<string, unknown> } }

export const apiStatus = (e: unknown) => (e as Failed | null)?.statusCode ?? (e as Failed | null)?.status ?? 0;
export const apiData = (e: unknown) => (e as Failed | null)?.data?.data ?? {};

export function apiError(e: unknown): string {
  const err = e as Failed | null;
  const status = apiStatus(e);
  if (!status) return "Нет связи с сайтом — проверь интернет и попробуй ещё раз";
  const msg = err?.data?.statusMessage || err?.data?.message || "";
  if (/[а-яё]/i.test(msg)) return msg;
  return status >= 500 ? "Что-то сломалось на сайте — попробуй через минуту" : "Не получилось — попробуй ещё раз";
}

// a change that needs signing in: the toast offers to sign in and come back
export function useNeedLogin() {
  const toast = useToast();
  const route = useRoute();
  return (what: string) => toast(`${what} — нужно войти`, { action: { label: "Войти", run: () => navigateTo({ path: "/login", query: { next: route.fullPath } }) } });
}
