import type { Manifest } from "./types";

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

export function loadData<T>(path: string): Promise<T> {
  let request = requests.get(path);
  if (!request) {
    request = fetch(dataUrl(path))
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            `Could not load game data (${response.status}). Please retry.`,
          );
        return response.json();
      })
      .catch((error: unknown) => {
        requests.delete(path);
        throw error;
      });
    requests.set(path, request);
  }
  return request as Promise<T>;
}

export async function loadManifest(): Promise<Manifest> {
  const manifest = await loadData<Manifest>("manifest.json");
  if (manifest.schema_version !== 1 || !Array.isArray(manifest.games)) {
    throw new Error(
      "This data version is not supported. Reload to update the app.",
    );
  }
  return manifest;
}
