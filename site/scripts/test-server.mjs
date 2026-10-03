// A test server the way the real site runs: the production build on Cloudflare's engine (wrangler dev, workerd)
// with its own local D1 and R2 in .wrangler/test (apart from `npm run dev`'s). TEST_SERVER=1 opens the sign-in by a
// nick and the example builds, put in when the base is empty. Nothing leaves this computer.
// Usage: npm run test-server [-- --no-build]   ->   http://localhost:8788
import { spawn, spawnSync } from "node:child_process";

const PORT = process.env.PORT || "8788";
const STATE = ".wrangler/test";
const BASE = `http://localhost:${PORT}`;
const sh = (cmd) => { const r = spawnSync(cmd, { stdio: "inherit", shell: true }); if (r.status) process.exit(r.status ?? 1); };

if (!process.argv.includes("--no-build")) sh("npx nuxt build");
sh(`npx wrangler d1 migrations apply poe2lab --local --persist-to ${STATE}`);
const server = spawn(`npx wrangler dev .output/server/index.mjs --assets .output/public --port ${PORT} --persist-to ${STATE} --var TEST_SERVER:1`,
  { stdio: "inherit", shell: true });
server.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => server.kill(sig));

// once it answers: the example builds into an empty base
for (let i = 0; i < 120; i++) {
  await new Promise((r) => setTimeout(r, 1000));
  let home;
  try { home = await (await fetch(`${BASE}/api/home`)).json(); } catch { continue; }
  if (!Object.keys(home.classes ?? {}).length) {
    const res = await fetch(`${BASE}/api/dev/seed`, { method: "POST", headers: { origin: BASE } });
    console.log(res.ok ? `test server: example builds put in (${(await res.json()).builds})` : `test server: seeding failed (${res.status})`);
  }
  console.log(`test server: ${BASE}  (sign in by a nick on /login)`);
  break;
}
