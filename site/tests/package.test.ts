import { describe, expect, it } from "vitest";
import { checkPackage, visibleLength, type BuildPackage } from "~~/shared/package";

const good = (): BuildPackage => ({
  v: 1, app: "poe2lab 0.9", key: "k1", patch: "0.5.5", title: "Ледяной удар", tags: ["бюджет"], cls: "monk", asc: "Заклинатель",
  mainSkill: "Ледяной удар", skillIcon: "ice-strike", dmg: "cold", weapon: "боевой посох",
  numbers: { dps: 312400, life: 1, es: 3640, res: { fire: 66, cold: 75, light: 75, chaos: "imm" }, defence: { value: 12035, kind: "уклонение" } },
  description: "Бей [[skill:ice-strike]] по боссам.", cards: { "skill:ice-strike": { kind: "skill", name: "Ледяной удар", img: "ice-strike" } },
  main: { name: "Ледяной удар", supports: [] }, groups: [], gear: [{ slot: "Шлем", pos: "helmet", label: "Шлем", img: "i-helmet" }], pob: "eN..",
});

describe("the publish package", () => {
  it("takes a good one", () => expect(checkPackage(good())).toEqual([]));
  it("counts what the reader sees: a piece by its name", () => {
    const p = good();
    expect(visibleLength(p.description, p.cards)).toBe("Бей Ледяной удар по боссам.".length);
  });
  it.each([
    ["an unknown class", { cls: "paladin" }],
    ["a tag the site does not have", { tags: ["имба"] }],
    ["too many tags", { tags: ["бюджет", "SSF", "боссы", "маппинг", "новичкам", "старт лиги"] }],
    ["a patch in another form", { patch: "latest" }],
    ["no numbers", { numbers: { dps: Number.NaN } }],
    ["a picture from elsewhere", { skillIcon: "https://evil.example/x.png" }],
    ["a piece without its card", { description: "Бей [[skill:flicker]]" }],
    ["no PoB code", { pob: "" }],
  ])("refuses %s", (_, patch) => expect(checkPackage({ ...good(), ...patch } as never).length).toBeGreaterThan(0));
  it("refuses a description too long and a package too big", () => {
    expect(checkPackage({ ...good(), description: "a".repeat(1501) })).toContain("описание длиннее 1500 знаков");
    expect(checkPackage(good(), "x".repeat(300_001))[0]).toMatch(/больше/);
  });
  it("takes the game CDN's pictures", () => expect(checkPackage({ ...good(), skillIcon: "https://web.poecdn.com/gen/image/x.png" })).toEqual([]));
});
