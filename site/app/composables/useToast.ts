// A short message at the bottom of the page: what happened, and maybe one action ("Отменить", "Повторить").
export interface ToastMsg { text: string; bad?: boolean; action?: { label: string; run: () => void }; id: number }

export const useToasts = () => useState<ToastMsg[]>("toasts", () => []);

export function useToast() {
  const list = useToasts();
  return (text: string, opts: { bad?: boolean; action?: ToastMsg["action"]; ms?: number } = {}) => {
    const id = Date.now() + Math.random();
    list.value = [...list.value, { text, bad: opts.bad, action: opts.action, id }];
    setTimeout(() => { list.value = list.value.filter((x) => x.id !== id); }, opts.ms ?? (opts.action ? 10000 : 4000));
  };
}
