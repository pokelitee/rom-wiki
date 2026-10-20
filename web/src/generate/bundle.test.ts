import { expect, it } from "vitest";
import { decodeWiki, encodeWiki, wikiFromBundle } from "./bundle";

const ID = "local-0123456789ab";
const encoder = new TextEncoder();

function bundle(id = ID, extra: Record<string, string> = {}) {
  const manifest = {
    schema_version: 1,
    games: [{ id, name: "Pokémon Emerald", sections: {} }],
    local: { profile: "emerald-us", verified: false, rom_sha256: "f".repeat(64) },
  };
  return new Map<string, Uint8Array>([
    ["manifest.json", encoder.encode(JSON.stringify(manifest))],
    [`${id}/pokemon/index-1.json`, encoder.encode('{"records":[]}')],
    ...Object.entries(extra).map(
      ([path, text]) => [path, encoder.encode(text)] as [string, Uint8Array],
    ),
  ]);
}

it("turns a generated bundle into a library entry and its files", () => {
  const { wiki, files } = wikiFromBundle(bundle(), "generator", "2026-10-20");

  expect(wiki).toMatchObject({
    id: ID,
    profile: "emerald-us",
    verified: false,
    generator: "generator",
    createdAt: "2026-10-20",
  });
  expect([...files.keys()]).toEqual([`${ID}/pokemon/index-1.json`]);
});

it("round-trips a wiki through an export file", async () => {
  const { wiki, files } = wikiFromBundle(bundle(), "generator");
  files.set(`${ID}/downloads/pokemon.json.gz`, new Uint8Array([0, 255, 31]));

  const decoded = await decodeWiki(await encodeWiki(wiki, files));

  expect(decoded.wiki).toEqual(wiki);
  expect(decoded.files).toEqual(files);
});

it("rejects wikis that could shadow other data", async () => {
  expect(() => wikiFromBundle(bundle("platinum"), "generator")).toThrow(
    "not a locally generated",
  );
  expect(() =>
    wikiFromBundle(bundle(ID, { "platinum/manifest.json": "{}" }), "generator"),
  ).toThrow("outside itself");
  expect(() =>
    wikiFromBundle(bundle(ID, { [`${ID}/../platinum/x.json`]: "{}" }), "g"),
  ).toThrow("outside itself");
});

it("rejects files that are not exports", async () => {
  await expect(decodeWiki(new Blob(["not gzip"]))).rejects.toThrow(
    "not a ROM Wiki export",
  );
  const other = await new Response(
    new Blob([JSON.stringify({ format: "something-else" })])
      .stream()
      .pipeThrough(new CompressionStream("gzip")),
  ).blob();
  await expect(decodeWiki(other)).rejects.toThrow("not a ROM Wiki export");
});
