import type { Game, Manifest } from "./types";
import { LOCAL_ID } from "../generate/bundle";
import { listWikis, readWikiFile } from "../generate/store";

const requests = new Map<string, Promise<unknown>>();

export function dataUrl(path: string): string {
  if (
    path.startsWith("/") ||
    path.split("/").includes("..") ||
    path.includes(":")
  ) {
    throw new Error("Invalid data path");
  }
  return `${import.meta.env.BASE_URL}data/${path}`;
}

/** Whether `path` belongs to a wiki generated in this browser. */
export function isLocalPath(path: string): boolean {
  return LOCAL_ID.test(path.split("/", 1)[0]);
}

export function loadData<T>(path: string): Promise<T> {
  let request = requests.get(path);
  if (!request) {
    request = (isLocalPath(path) ? loadLocal(path) : loadPublished(path)).catch(
      (error: unknown) => {
        requests.delete(path);
        throw error;
      },
    );
    requests.set(path, request);
  }
  return request as Promise<T>;
}

async function loadPublished(path: string): Promise<unknown> {
  const response = await fetch(dataUrl(path));
  if (!response.ok)
    throw new Error(
      `Could not load game data (${response.status}). Please retry.`,
    );
  return response.json();
}

async function loadLocal(path: string): Promise<unknown> {
  if (path.split("/").includes("..")) throw new Error("Invalid data path");
  return JSON.parse(new TextDecoder().decode(await readWikiFile(path)));
}

/** Drop cached resources of a local wiki that was replaced or deleted. */
export function forgetLocalData(id: string): void {
  for (const path of requests.keys())
    if (path.startsWith(`${id}/`)) requests.delete(path);
}

export async function loadManifest(): Promise<Manifest> {
  const manifest = await loadData<Manifest>("manifest.json");
  if (manifest.schema_version !== 1 || !Array.isArray(manifest.games)) {
    throw new Error(
      "This data version is not supported. Reload to update the app.",
    );
  }
  return { ...manifest, games: [...manifest.games, ...(await localGames())] };
}

async function localGames(): Promise<Game[]> {
  let wikis;
  try {
    wikis = await listWikis();
  } catch (error) {
    // Without storage (some private windows), the library is just the
    // published games.
    console.warn("Locally generated wikis are unavailable", error);
    return [];
  }
  if (!wikis.length) return [];
  const generator = await currentGenerator();
  return wikis.map((wiki) => ({
    ...wiki.game,
    local: {
      verified: wiki.verified,
      profile: wiki.profile,
      createdAt: wiki.createdAt,
      outdated: generator !== undefined && generator !== wiki.generator,
    },
  }));
}

/** The SHA-256 of the generator the site serves now, if it can be read. */
export async function currentGenerator(): Promise<string | undefined> {
  try {
    const response = await fetch(
      `${import.meta.env.BASE_URL}generator/manifest.json`,
    );
    if (!response.ok) return undefined;
    const manifest = (await response.json()) as { wheel: { sha256: string } };
    return manifest.wheel.sha256;
  } catch {
    return undefined;
  }
}
