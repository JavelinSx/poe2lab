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

// a picture of the game (development: public/game, git-ignored; the real site: the game's CDN)
export const gameArt = (name: string) => `/game/${name}.png`;
