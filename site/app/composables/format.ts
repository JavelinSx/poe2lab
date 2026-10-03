// Numbers and words the way the pages show them (Russian: a space between thousands, a comma for decimals).
export const fmtInt = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/ /g, " ");
export const fmtRating = (r: number) => r.toFixed(1).replace(".", ",");

// "38 отзывов", "1 отзыв", "2 отзыва"
export function plural(n: number, one: string, few: string, many: string) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}

// the avatar's letters until there is a Discord picture
export const initials = (nick: string) => (nick.replace(/[^A-Za-zА-Яа-я]/g, "").slice(0, 2) || "??").toUpperCase();

// a picture of the game: the game CDN's address as it is, a name from public/game (development only, git-ignored)
export const gameArt = (name: string) => (/^https:\/\//.test(name) ? name : `/game/${name}.png`);

// when, the way people say it: "только что", "3 часа назад", "вчера", "5 дней назад", "12 сентября"
const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
export function fmtWhen(sec: number) {
  const d = new Date(sec * 1000), now = new Date();
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((day(now) - day(d)) / 86_400_000);
  if (days <= 0) {
    const h = Math.floor((now.getTime() - d.getTime()) / 3_600_000);
    return h < 1 ? "только что" : `${h} ${plural(h, "час", "часа", "часов")} назад`;
  }
  if (days === 1) return "вчера";
  if (days < 7) return `${days} ${plural(days, "день", "дня", "дней")} назад`;
  return fmtDate(sec);
}
// "12 сентября", with the year when it is not this one
export function fmtDate(sec: number) {
  const d = new Date(sec * 1000);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}${d.getFullYear() !== new Date().getFullYear() ? ` ${d.getFullYear()}` : ""}`;
}
// "с марта 2026"
export const fmtSince = (sec: number) => { const d = new Date(sec * 1000); return `с ${MONTHS[d.getMonth()]} ${d.getFullYear()}`; };
// a card's "updated" (YYYY-MM-DD) as seconds
export const daySec = (iso: string) => Math.floor(new Date(iso).getTime() / 1000);
