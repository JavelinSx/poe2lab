// poe2lab feedback relay (Cloudflare Worker). The app posts a report here; the worker checks it and mails it to
// FEEDBACK_TO through Resend. The Resend key is a Worker secret, so it never ships with the app.
//
// Why this is not a spam relay:
// - the recipient is fixed in the Worker settings, never taken from the request;
// - Resend without a verified domain delivers only to the account's own address anyway;
// - every report must carry a real Path of Building (PoE2) code, checked by decompressing it;
// - rate limits per IP and overall, size limits on every field, plain-text mail only.

const MAX_BODY = 10 * 1024 * 1024;
const MAX_MESSAGE = 5000;
const MAX_CONTACT = 200;
const MAX_CODE = 300 * 1024;
const MAX_JSON = 64 * 1024;
const MAX_IMAGES = 3;
const MAX_IMAGE = 3 * 1024 * 1024;
const IMAGE_TYPES = {
  png: { mime: "image/png", magic: [0x89, 0x50, 0x4e, 0x47] },
  jpg: { mime: "image/jpeg", magic: [0xff, 0xd8, 0xff] },
  webp: { mime: "image/webp", magic: [0x52, 0x49, 0x46, 0x46] },
};
const EMAIL = /^[^\s@<>()",;]{1,64}@[^\s@<>()",;]{1,190}\.[a-z]{2,}$/i;

const reply = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json; charset=utf-8" },
});

class Bad extends Error {}

function base64Bytes(text) {
  const clean = String(text).replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(clean + "=".repeat((4 - (clean.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function bytesBase64(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

// A PoB code is zlib-compressed build XML in url-safe base64; read just enough to see a PoE2 build in it.
async function pobBuild(code) {
  if (typeof code !== "string" || code.length < 100 || code.length > MAX_CODE) throw new Bad("build code missing");
  let head;
  try {
    const stream = new Blob([base64Bytes(code)]).stream().pipeThrough(new DecompressionStream("deflate"));
    const reader = stream.pipeThrough(new TextDecoderStream()).getReader();
    head = "";
    while (head.length < 4096) {
      const { value, done } = await reader.read();
      if (done) break;
      head += value;
    }
    reader.cancel().catch(() => {});
  } catch (_) {
    throw new Bad("not a Path of Building code");
  }
  if (!head.includes("<PathOfBuilding2")) throw new Bad("not a Path of Building (PoE2) build");
  const tag = head.match(/<Build\s[^>]*>/)?.[0] || "";
  const attr = (name) => (tag.match(new RegExp(`\\b${name}="([^"]{0,40})"`)) || [])[1] || "";
  return { class: attr("ascendClassName") || attr("className") || "?", level: attr("level") || "?" };
}

function image(item, i) {
  const ext = String(item?.type || "").toLowerCase();
  const kind = IMAGE_TYPES[ext];
  if (!kind || typeof item.data !== "string") throw new Bad(`image ${i + 1}: png, jpg or webp only`);
  if (item.data.length > Math.ceil(MAX_IMAGE / 3) * 4 + 8) throw new Bad(`image ${i + 1} is larger than 3 MB`);
  const bytes = base64Bytes(item.data);
  if (!kind.magic.every((b, k) => bytes[k] === b)) throw new Bad(`image ${i + 1} is not a ${ext}`);
  return { filename: `screenshot-${i + 1}.${ext}`, content: bytesBase64(bytes) };
}

function smallJson(value, name) {
  if (value === undefined || value === null) return null;
  const text = JSON.stringify(value, null, 2);
  if (text.length > MAX_JSON) throw new Bad(`${name} is too large`);
  return text;
}

const oneLine = (s, n) => String(s).replace(/[\r\n\t]+/g, " ").replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, n);

export async function handle(request, env) {
  const url = new URL(request.url);
  if (url.pathname !== "/feedback") return reply(404, { error: "not found" });
  if (request.method !== "POST") return reply(405, { error: "POST only" });
  // no CORS headers are ever sent, and this header forces a preflight: web pages cannot post here
  if (request.headers.get("X-Poe2lab-Feedback") !== "1") return reply(403, { error: "forbidden" });
  if (!(request.headers.get("Content-Type") || "").startsWith("application/json")) {
    return reply(415, { error: "JSON only" });
  }
  if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY) return reply(413, { error: "too large" });
  if (!env.RESEND_API_KEY || !env.FEEDBACK_TO) return reply(503, { error: "feedback is not configured" });

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  for (const [limiter, key] of [[env.PER_IP, ip], [env.GLOBAL, "all"]]) {
    if (limiter && !(await limiter.limit({ key })).success) {
      return reply(429, { error: "too many reports, try again in a minute" });
    }
  }

  let body;
  try {
    const raw = await request.text();
    if (raw.length > MAX_BODY) return reply(413, { error: "too large" });
    body = JSON.parse(raw);
  } catch (_) {
    return reply(400, { error: "bad JSON" });
  }

  let mail;
  try {
    mail = await compose(body || {}, env);
  } catch (err) {
    if (err instanceof Bad) return reply(400, { error: err.message });
    throw err;
  }

  const sent = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(mail),
  });
  if (!sent.ok) {
    console.log("resend", sent.status, (await sent.text()).slice(0, 500));
    return reply(502, { error: "mail service refused the report" });
  }
  return reply(200, { ok: true });
}

async function compose(body, env) {
  const message = typeof body.message === "string" ? body.message.trim() : "";
  if (message.length < 5) throw new Bad("message is empty");
  if (message.length > MAX_MESSAGE) throw new Bad(`message is longer than ${MAX_MESSAGE} characters`);
  const contact = oneLine(body.contact || "", MAX_CONTACT);

  const build = body.build || {};
  const info = await pobBuild(build.code);
  const attachments = [{ filename: "build.txt", content: bytesBase64(new TextEncoder().encode(build.code)) }];
  if (build.planCode) {
    await pobBuild(build.planCode);
    attachments.push({ filename: "build-with-tree-plan.txt",
      content: bytesBase64(new TextEncoder().encode(build.planCode)) });
  }
  for (const [name, value] of [["profile.json", body.profile], ["context.json", body.context]]) {
    const text = smallJson(value, name);
    if (text) attachments.push({ filename: name, content: bytesBase64(new TextEncoder().encode(text)) });
  }
  const images = Array.isArray(body.images) ? body.images : [];
  if (images.length > MAX_IMAGES) throw new Bad(`at most ${MAX_IMAGES} screenshots`);
  images.forEach((item, i) => attachments.push(image(item, i)));

  const ctx = body.context && typeof body.context === "object" ? body.context : {};
  const lines = [
    message, "",
    "---",
    `build: ${oneLine(build.name || "?", 80)} (${info.class} ${info.level})`,
    `tab: ${oneLine(ctx.tab || "?", 40)}, goal: ${oneLine(ctx.mode || "?", 20)}, ` +
      `skill: ${oneLine(ctx.mainSkill || "?", 80)}, lang: ${oneLine(ctx.lang || "?", 5)}`,
    `poe2lab: ${oneLine(ctx.version || "?", 60)}`,
    `contact: ${contact || "—"}`,
    "Attached: build.txt (PoB code, paste it into Path of Building or poe2lab), profile, context, screenshots.",
  ];
  const mail = {
    from: env.FEEDBACK_FROM || "poe2lab <onboarding@resend.dev>",
    to: [env.FEEDBACK_TO],
    subject: `[poe2lab] ${info.class} ${info.level}: ${oneLine(message, 70)}`,
    text: lines.join("\n"),
    attachments,
  };
  if (EMAIL.test(contact)) mail.reply_to = contact;
  return mail;
}

export default {
  async fetch(request, env) {
    try {
      return await handle(request, env);
    } catch (err) {
      console.log("error", err && err.stack);
      return reply(500, { error: "internal error" });
    }
  },
};
