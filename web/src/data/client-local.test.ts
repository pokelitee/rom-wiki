import { afterEach, expect, it, vi } from "vitest";
import type { LocalWiki } from "../generate/store";

const ID = "local-0123456789ab";
const stored = new Map<string, Uint8Array>();
const wikis: LocalWiki[] = [];

vi.mock("../generate/store", () => ({
  readWikiFile: async (path: string) => {
    const data = stored.get(path);
    if (!data) throw new Error("missing");
    return data;
  },
  listWikis: async () => wikis,
}));

const { forgetLocalData, isLocalPath, loadData, loadManifest } = await import(
  "./client"
);

afterEach(() => {
  vi.unstubAllGlobals();
  stored.clear();
  wikis.length = 0;
});

it("recognizes only local wiki paths", () => {
  expect(isLocalPath(`${ID}/pokemon/index.json`)).toBe(true);
  expect(isLocalPath("platinum/pokemon/index.json")).toBe(false);
  expect(isLocalPath("local-nothex/pokemon/index.json")).toBe(false);
});

it("reads local wiki resources from storage, not the network", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  stored.set(
    `${ID}/pokemon/index.json`,
    new TextEncoder().encode('{"records":[1]}'),
  );

  await expect(loadData(`${ID}/pokemon/index.json`)).resolves.toEqual({
    records: [1],
  });
  expect(fetcher).not.toHaveBeenCalled();

  stored.set(
    `${ID}/pokemon/index.json`,
    new TextEncoder().encode('{"records":[2]}'),
  );
  forgetLocalData(ID);
  await expect(loadData(`${ID}/pokemon/index.json`)).resolves.toEqual({
    records: [2],
  });
});

it("adds this browser's wikis to the library", async () => {
  wikis.push({
    id: ID,
    game: { id: ID, name: "Pokémon Emerald" } as LocalWiki["game"],
    profile: "emerald-us",
    verified: false,
    romSha256: "f".repeat(64),
    generator: "old-generator",
    createdAt: "2026-10-20T00:00:00Z",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("generator/manifest.json")
          ? { wheel: { sha256: "new-generator" } }
          : { schema_version: 1, games: [{ id: "platinum" }] },
    })),
  );

  const manifest = await loadManifest();

  expect(manifest.games.map((game) => game.id)).toEqual(["platinum", ID]);
  expect(manifest.games[1].local).toEqual({
    verified: false,
    profile: "emerald-us",
    createdAt: "2026-10-20T00:00:00Z",
    outdated: true,
  });
});
