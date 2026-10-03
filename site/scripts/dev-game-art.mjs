// The game's pictures for the mock pages, from the design's copy of the app's icon cache (both outside git):
// GGG's art is not kept in the repository, the real site takes it from the game's CDN.
import fs from "node:fs";
import path from "node:path";
const from = path.resolve(import.meta.dirname, "../../design/redesign/assets/game");
const to = path.resolve(import.meta.dirname, "../public/game");
if (!fs.existsSync(from)) { console.log("no", from, "- the mock pages show placeholders"); process.exit(0); }
fs.mkdirSync(to, { recursive: true });
let n = 0;
for (const f of fs.readdirSync(from)) if (f.endsWith(".png")) { fs.copyFileSync(path.join(from, f), path.join(to, f)); n++; }
console.log("copied", n, "pictures to", to);
