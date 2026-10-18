import { describe, expect, it } from "vitest";
import type { IndexRecord } from "../../data/types";
import { recordContext, sharedLabels } from "./same-name";

function row(id: string, label: string, fields: IndexRecord["fields"] = {}) {
  return { id, label, chunk: "", fields } as IndexRecord;
}

describe("records with the same name", () => {
  it("finds labels shared within a section", () => {
    expect(
      sharedLabels([
        row("a", "Mt. Coronet"),
        row("b", "Mt. Coronet"),
        row("c", "Eterna City"),
      ]),
    ).toEqual(new Set(["Mt. Coronet"]));
  });

  it("tells trainers apart by level, party, and number", () => {
    expect(
      recordContext(
        "trainers",
        row("trainer-0117", "Camper Mickey", {
          min_level: 5,
          max_level: 7,
          pokemon: ["Rattata", "Starly", "Bidoof", "Shinx"],
        }),
      ),
    ).toBe("Lv. 5–7 · Rattata, Starly, Bidoof +1 · #117");
  });

  it("leaves out what catalog columns already show", () => {
    const marsh = row("area-023", "Great Marsh", {
      min_level: 3,
      max_level: 55,
      methods: ["walking", "surf"],
      pokemon: ["Bibarel", "Wooper"],
    });
    expect(recordContext("encounters", marsh, ["levels", "methods"])).toBe(
      "Bibarel, Wooper · #23",
    );
    expect(recordContext("encounters", marsh)).toBe(
      "Lv. 3–55 · Walking, Surf · #23",
    );
  });

  it("names Gen 4 indoor maps by their map code", () => {
    const place = (code: string) =>
      recordContext(
        "locations",
        row("header-006", "Jubilife City", { section_name: code }),
      );
    expect(place("C01PC0101")).toBe("Pokémon Center · Map 6");
    expect(place("C01FS0101")).toBe("Poké Mart · Map 6");
    expect(place("C01GYM0101")).toBe("Gym · Map 6");
    expect(place("C01R0501")).toBe("Building · Map 6");
    expect(place("C01")).toBe("Map 6");
    expect(recordContext("locations", row("header-028", "Castelia City"))).toBe(
      "Map 28",
    );
  });

  it("summarizes encounter areas by level and method", () => {
    expect(
      recordContext(
        "encounters",
        row("area-011", "Mt. Coronet", {
          min_level: 30,
          max_level: 39,
          methods: ["walking", "special"],
        }),
      ),
    ).toBe("Lv. 30–39 · Walking, Special · #11");
  });

  it("falls back to the record's own identifier", () => {
    expect(
      recordContext("items", row("xtransceiver-621", "Xtransceiver")),
    ).toBe("#621");
    expect(recordContext("pokemon", row("nidoran-f", "Nidoran"))).toBe(
      "nidoran-f",
    );
  });
});
