// node --test worker/feedback.test.mjs  — the relay's checks, with Resend replaced by a stub
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { handle } from "./feedback.js";

const CODE = readFileSync(new URL("../tests/fixtures/titan.txt", import.meta.url), "utf8").trim();
const PNG = Buffer.from("89504e470d0a1a0a0000000d49484452", "hex").toString("base64");
const env = (extra = {}) => ({ RESEND_API_KEY: "k", FEEDBACK_TO: "owner@example.com", ...extra });
let sent;
globalThis.fetch = async (url, init) => { sent = { url, body: JSON.parse(init.body) }; return new Response("{}"); };

const post = (body, headers = {}) => new Request("https://relay.test/feedback", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Poe2lab-Feedback": "1", "CF-Connecting-IP": "1.2.3.4", ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
});
const report = (extra = {}) => ({
  message: "DPS on the damage tab differs from PoB", contact: "player@example.com",
  build: { name: "titan", code: CODE }, profile: { rage: 60 },
  context: { tab: "damage", mode: "balanced", mainSkill: "Furious Slam", lang: "ru", version: "abc" },
  images: [{ type: "png", data: PNG }], ...extra,
});

test("a real report is mailed to the fixed address with the build attached", async () => {
  sent = null;
  const res = await handle(post(report({ to: "victim@example.com" })), env());
  assert.equal(res.status, 200);
  assert.equal(sent.url, "https://api.resend.com/emails");
  assert.deepEqual(sent.body.to, ["owner@example.com"]);
  assert.equal(sent.body.reply_to, "player@example.com");
  assert.match(sent.body.subject, /^\[poe2lab\] Titan 95: DPS on the damage tab/);
  const files = sent.body.attachments.map((a) => a.filename);
  assert.deepEqual(files, ["build.txt", "profile.json", "context.json", "screenshot-1.png"]);
  assert.equal(Buffer.from(sent.body.attachments[0].content, "base64").toString(), CODE);
});

test("anything without a real PoB code is refused before mailing", async () => {
  for (const code of [undefined, "x".repeat(200), Buffer.from("hello".repeat(40)).toString("base64")]) {
    sent = null;
    const res = await handle(post(report({ build: { code } })), env());
    assert.equal(res.status, 400);
    assert.equal(sent, null);
  }
});

test("fake images, too many images and empty messages are refused", async () => {
  const cases = [
    report({ images: [{ type: "png", data: Buffer.from("GIF89a....").toString("base64") }] }),
    report({ images: [{ type: "svg", data: PNG }] }),
    report({ images: Array(4).fill({ type: "png", data: PNG }) }),
    report({ message: "  " }),
  ];
  for (const body of cases) assert.equal((await handle(post(body), env())).status, 400);
});

test("pages elsewhere, other methods and an unconfigured worker are refused", async () => {
  assert.equal((await handle(post(report(), { "X-Poe2lab-Feedback": "" }), env())).status, 403);
  assert.equal((await handle(new Request("https://relay.test/feedback"), env())).status, 405);
  assert.equal((await handle(post(report()), env({ RESEND_API_KEY: "" }))).status, 503);
  assert.equal((await handle(post("{oops"), env())).status, 400);
});

test("the rate limit stops a flood", async () => {
  let n = 0;
  const PER_IP = { limit: async () => ({ success: ++n <= 2 }) };
  const codes = [];
  for (let i = 0; i < 3; i++) codes.push((await handle(post(report()), env({ PER_IP }))).status);
  assert.deepEqual(codes, [200, 200, 429]);
});

test("line breaks cannot leak into the subject", async () => {
  await handle(post(report({ message: "first line\nBcc: x@y.z\r\nmore" })), env());
  assert.ok(!/[\r\n]/.test(sent.body.subject));
});
