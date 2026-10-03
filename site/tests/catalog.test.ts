import { describe, expect, it } from "vitest";
import { readQuery, where } from "~~/server/utils/catalog";

describe("the catalog's query", () => {
  it("keeps only known values from the address", () => {
    const q = readQuery({ cls: "paladin", dmg: ["cold", "void"], tag: ["SSF", "имба"], weapon: "лук", sort: "evil", limit: "999" });
    expect(q).toMatchObject({ cls: undefined, dmg: ["cold"], tag: ["SSF"], weapon: ["лук"], sort: "rating", limit: 48, patch: "current" });
  });
  it("turns known words into filters and the rest into a search, all as parameters", () => {
    const w = where(readQuery({ q: "холод посох каскад", cls: "monk" }));
    expect(w.sql).toContain("b.cls = ?");
    expect(w.sql).toContain("b.dmg = ?");
    expect(w.sql).toContain("b.weapon = ?");
    expect(w.sql).toContain("b.search LIKE ?");
    expect(w.args).toEqual(["monk", "0.5.5", "cold", "боевой посох", "%каскад%"]);
  });
  it("takes %, _ and quotes in a word literally", () => {
    const w = where(readQuery({ q: "100%_x'" }));
    expect(w.sql).not.toContain("100");
    expect(w.args).toContain("%100\\%\\_x'%");
  });
  it("leaves the ascendancies out for their own counts", () => {
    const c = readQuery({ cls: "monk", asc: ["Заклинатель"] });
    expect(where(c).sql).toContain("b.asc IN (?)");
    expect(where(c, "asc").sql).not.toContain("b.asc");
  });
});
