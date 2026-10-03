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

const one = (await anon.call("GET", "/api/builds?author=Inverno&patch=all")).data.builds[0];  // the seed's "Ледяной удар" (its title the run changes)
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

// favourites, follows and what follows from them
const favNoLogin = await anon.call("GET", "/api/builds?fav=1");
await reader.call("POST", `/api/favorites/${one.id}`);
await reader.call("POST", `/api/favorites/${one.id}`);
const favs = await reader.call("GET", "/api/builds?fav=1");
const marked = await reader.call("GET", `/api/builds/${one.id}`);
await reader.call("DELETE", `/api/favorites/${one.id}`);
const unfav = await reader.call("GET", "/api/builds?fav=1");
check("favourites: need signing in, kept once, taken off", favNoLogin.status === 401 && favs.data.total === 1 && marked.data.favorite === true && unfav.data.total === 0);
const selfFollow = await authorC.call("POST", "/api/follows/Inverno");
await reader.call("POST", "/api/follows/Inverno");
const followed = await reader.call("GET", `/api/builds/${one.id}`);
const pub3 = await app.call("POST", "/api/builds", { ...body, key: "smoke-2", title: "Проверка подписки" }, { authorization: `Bearer ${tok.data.token}` });
const news = await reader.call("GET", "/api/notifications");
check("following: not oneself; a new build reaches the followers", selfFollow.status === 400 && followed.data.author.following === true
  && news.data.some((n) => n.kind === "follow" && n.build?.id === pub3.data.id && n.actor === "Inverno"));
await authorC.call("POST", `/api/builds/${pub3.data.id}/state`, { state: "removed" });
await reader.call("DELETE", "/api/follows/Inverno");
const pob = await anon.call("GET", `/api/builds/${one.id}/pob`);
check("the PoB code on asking", pob.status === 200 && typeof pob.data.pob === "string" && pob.data.pob.length > 0);

// notifications: the author sees a new review and reads them all; the kinds they do not want are not counted
const fresh = new Client();
await fresh.call("POST", "/api/dev/login", { nick: "SmokeNotice" });
await fresh.call("PUT", `/api/builds/${one.id}/review`, { stars: 4, text: "Свежий отзыв" });
const authorNews = await authorC.call("GET", "/api/notifications");
const unreadBefore = (await authorC.call("GET", "/api/me")).data.unread;
await authorC.call("PATCH", "/api/me", { notify: { reviews: false, replies: true, follows: false } });
const unreadOff = (await authorC.call("GET", "/api/me")).data.unread;
await authorC.call("PATCH", "/api/me", { notify: { reviews: true, replies: true, follows: true } });
await authorC.call("POST", "/api/notifications/read");
await fresh.call("DELETE", "/api/me");
const unreadAfter = (await authorC.call("GET", "/api/me")).data.unread;
check("notifications: shown, filtered by the settings, read", authorNews.data.some((n) => n.kind === "review" && n.actor === "SmokeNotice" && n.fresh)
  && unreadBefore > 0 && unreadOff < unreadBefore && unreadAfter === 0);

// settings: a nick taken, links only of their sites, the app taken off
const taken = await reader.call("PATCH", "/api/me", { nick: "inverno" });
const badLink = await reader.call("PATCH", "/api/me", { links: [{ kind: "youtube", url: "javascript:alert(1)" }] });
const okLink = await reader.call("PATCH", "/api/me", { bio: "Проверка", links: [{ kind: "twitch", url: "twitch.tv/smoke" }] });
const st = await reader.call("GET", "/api/me/settings");
const nickFree = await anon.call("GET", "/api/nick?n=" + encodeURIComponent("Свободный_ник"));
const nickTaken = await anon.call("GET", "/api/nick?n=MapMama");
check("settings: nick taken, a bad link refused, a good one kept", taken.status === 409 && badLink.status === 400 && okLink.status === 200
  && st.data.links[0]?.url === "https://twitch.tv/smoke" && nickFree.data.free === true && nickTaken.data.free === false);
const apps = (await authorC.call("GET", "/api/me/settings")).data.apps;
const smokeApp = apps.find((x) => x.name === "poe2lab на SMOKE-PC");
await authorC.call("DELETE", `/api/me/apps/${smokeApp.id}`);
const revoked = await app.call("POST", "/api/builds", body, { authorization: `Bearer ${tok.data.token}` });
check("an app taken off cannot publish", revoked.status === 401);

// an account deleted: its review leaves the rating, its session ends
const temp = new Client();
await temp.call("POST", "/api/dev/login", { nick: "SmokeTemp" });
const ratingBefore = (await anon.call("GET", `/api/builds/${one.id}`)).data.card;
await temp.call("PUT", `/api/builds/${one.id}/review`, { stars: 1, text: "Удалюсь" });
await temp.call("DELETE", "/api/me");
const ratingAfter = (await anon.call("GET", `/api/builds/${one.id}`)).data.card;
const tempMe = await temp.call("GET", "/api/me");
check("an account deleted: its review leaves the rating", ratingAfter.reviews === ratingBefore.reviews && Math.abs(ratingAfter.rating - ratingBefore.rating) < 1e-9 && !tempMe.data);
await reader.call("POST", "/api/logout");
check("signed out", !(await reader.call("GET", "/api/me")).data);

console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
