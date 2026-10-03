// The API end to end against a running dev server (npm run dev; POST /api/dev/seed first): the catalog's filters,
// a build's page, an author, signing in (dev), a review and "helpful", the author's edit and answer, taking a build off
// and back, the app's connection by a code and publishing with its token. Exits non-zero on the first failure.
const BASE = process.env.BASE || "http://localhost:3100";
let failed = 0;
const check = (name, ok, extra = "") => { console.log(ok ? "ok  " : "FAIL", name, extra); if (!ok) failed++; };

class Client {
  constructor() { this.cookie = ""; }
  async call(method, path, body, headers = {}) {
    const res = await fetch(BASE + path, {
      method, headers: { "content-type": "application/json", origin: BASE, ...(this.cookie ? { cookie: this.cookie } : {}), ...headers },
      body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
    });
    const set = res.headers.get("set-cookie");
    if (set) this.cookie = set.split(";")[0];
    const text = await res.text();
    let data; try { data = JSON.parse(text); } catch { data = text; }
    return { status: res.status, data };
  }
}

const anon = new Client();
const cat = await anon.call("GET", "/api/builds?cls=monk&q=" + encodeURIComponent("холод"));
check("catalog: a class and a word that is a damage type", cat.status === 200 && cat.data.builds.every((b) => b.cls === "monk" && b.dmg === "cold"), `${cat.data.total} found`);
const words = await anon.call("GET", "/api/builds?q=" + encodeURIComponent("каскад"));
check("catalog: a free word in the title", words.data.builds.some((b) => /каскад/i.test(b.title)));
const tag = await anon.call("GET", "/api/builds?tag=" + encodeURIComponent("SSF") + "&patch=all");
check("catalog: a tag, every patch", tag.data.builds.length > 0 && tag.data.builds.every((b) => b.tags.includes("SSF")));
const odd = await anon.call("GET", "/api/builds?q=" + encodeURIComponent("100%_'\"; DROP TABLE builds"));
check("catalog: odd words are only words", odd.status === 200 && odd.data.total === 0);
const home = await anon.call("GET", "/api/home");
check("home: classes, shelves, authors", home.status === 200 && home.data.shelves.popular.length === 4 && home.data.authors.length > 0);

const one = (await anon.call("GET", "/api/builds?q=" + encodeURIComponent("Колокол бури"))).data.builds[0];
const page = await anon.call("GET", `/api/builds/${one.id}`);
check("a build's page: package, reviews, author", page.status === 200 && page.data.page.gear.length > 5 && page.data.reviews.n > 0 && page.data.author.nick === "Inverno");
const missing = await anon.call("GET", "/api/builds/nope1234");
check("a build that is not there: 404", missing.status === 404);
const author = await anon.call("GET", "/api/authors/MapMama");
check("an author's page", author.status === 200 && author.data.builds.length > 0);

const noReview = await anon.call("PUT", `/api/builds/${one.id}/review`, { stars: 5, text: "x" });
check("a review needs signing in", noReview.status === 401);
const foreign = await anon.call("PUT", `/api/builds/${one.id}/review`, { stars: 5, text: "x" }, { origin: "https://evil.example" });
check("a change from another site's page is refused", foreign.status === 403);

const reader = new Client();
await reader.call("POST", "/api/dev/login", { nick: "SmokeReader" });
const me = await reader.call("GET", "/api/me");
check("signed in (dev)", me.data && me.data.nick === "SmokeReader");
const rv = await reader.call("PUT", `/api/builds/${one.id}/review`, { stars: 4, crit: { dmg: 5, tank: 3, nope: 9 }, text: "Проверка отзыва", cls: "monk", level: 70 });
check("a review written", rv.status === 200 && rv.data.id);
const rv2 = await reader.call("PUT", `/api/builds/${one.id}/review`, { stars: 2, text: "Передумал" });
check("the same account changes its review", rv2.status === 200 && rv2.data.updated === true);
const after = await reader.call("GET", `/api/builds/${one.id}/reviews?sort=new`);
const mine = after.data.items.find((r) => r.own);
check("the review is there, criteria filtered", mine && mine.stars === 2 && after.data.mine.text === "Передумал");

const authorC = new Client();
await authorC.call("POST", "/api/dev/login", { nick: "Inverno" });
const selfReview = await authorC.call("PUT", `/api/builds/${one.id}/review`, { stars: 5, text: "Мой билд лучший" });
check("the author cannot review their own build", selfReview.status === 403);
const vote = await authorC.call("POST", `/api/reviews/${mine.id}/helpful`);
const unvote = await authorC.call("POST", `/api/reviews/${mine.id}/helpful`);
check("helpful is a toggle", vote.data.voted === true && unvote.data.voted === false);
const ownVote = await reader.call("POST", `/api/reviews/${mine.id}/helpful`);
check("no vote on one's own review", ownVote.status === 403);
const reply = await authorC.call("POST", `/api/reviews/${mine.id}/reply`, { text: "Спасибо!" });
const notReply = await reader.call("POST", `/api/reviews/${mine.id}/reply`, { text: "я не автор" });
check("the author answers, nobody else", reply.status === 200 && notReply.status === 403);
const edit = await authorC.call("PATCH", `/api/builds/${one.id}`, { title: "Ледяной удар — правка", tags: ["старт лиги", "SSF"], description: "Бей [[skill:ice-strike]] и [[term:x]]" });
check("an edit with a piece that has no card is refused", edit.status === 400);
const edit2 = await authorC.call("PATCH", `/api/builds/${one.id}`, { title: "Ледяной удар — правка", tags: ["старт лиги", "SSF"], description: "Бей [[skill:ice-strike]]." });
const page2 = await anon.call("GET", `/api/builds/${one.id}`);
check("the author's edit is on the page", edit2.status === 200 && page2.data.card.title === "Ледяной удар — правка" && page2.data.card.tags.includes("SSF"));
const notMine = await reader.call("PATCH", `/api/builds/${one.id}`, { title: "чужой", tags: [] });
check("nobody else edits it", notMine.status === 403);
await authorC.call("POST", `/api/builds/${one.id}/state`, { state: "hidden" });
const hidden = await anon.call("GET", `/api/builds/${one.id}`);
const seenByAuthor = await authorC.call("GET", `/api/builds/${one.id}`);
await authorC.call("POST", `/api/builds/${one.id}/state`, { state: "published" });
check("taken off: 410 to others, the author still sees it", hidden.status === 410 && seenByAuthor.status === 200);

// the app: a code, the player allows it, the app takes its token and publishes
const app = new Client();
const start = await app.call("POST", "/api/device/start", { name: "poe2lab на SMOKE-PC" });
const waiting = await app.call("POST", "/api/device/token", { device: start.data.device });
check("the app waits for the player", start.status === 200 && /^[A-Z0-9]{6}$/.test(start.data.code) && waiting.status === 202);
const shown = await authorC.call("GET", `/api/device/${start.data.code}`);
await authorC.call("POST", "/api/device/confirm", { code: start.data.code, allow: true });
const tok = await app.call("POST", "/api/device/token", { device: start.data.device });
const again = await app.call("POST", "/api/device/token", { device: start.data.device });
check("allowed: the token once", shown.data.name === "poe2lab на SMOKE-PC" && tok.status === 200 && tok.data.token && again.status === 410);
const pkg = (await anon.call("GET", `/api/builds/${one.id}`)).data;
const body = { v: 1, app: "smoke", key: "smoke-1", patch: "0.5.5", title: "Проверка публикации", tags: ["бюджет"], cls: "monk", asc: "Заклинатель",
  mainSkill: "Ледяной удар", skillIcon: "ice-strike", dmg: "cold", weapon: "боевой посох", numbers: pkg.page.numbers, description: "Коротко: [[skill:ice-strike]].",
  cards: pkg.page.cards, main: pkg.page.main, groups: pkg.page.groups, gear: pkg.page.gear, pob: "eN-smoke" };
const pub = await app.call("POST", "/api/builds", body, { authorization: `Bearer ${tok.data.token}` });
const pub2 = await app.call("POST", "/api/builds", { ...body, title: "Проверка публикации 2" }, { authorization: `Bearer ${tok.data.token}` });
check("published with the token; again updates the same build", pub.status === 200 && pub2.data.id === pub.data.id && pub2.data.version === 2);
const bad = await app.call("POST", "/api/builds", { ...body, cls: "paladin", tags: ["???"] }, { authorization: `Bearer ${tok.data.token}` });
const noTok = await app.call("POST", "/api/builds", body, { authorization: "Bearer wrong" });
check("a bad package and a wrong token are refused", bad.status === 400 && noTok.status === 401);
await authorC.call("POST", `/api/builds/${pub.data.id}/state`, { state: "removed" });
const gone = await anon.call("GET", `/api/builds/${pub.data.id}`);
check("deleted for good", gone.status === 404);

console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
