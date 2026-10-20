import type { Game } from "../data/types";

// What the library shows about a wiki generated in this browser.
export interface LocalWiki {
  id: string;
  game: Game;
  profile: string;
  // False when no profile knows the ROM and it was read as the retail game
  // its header names.
  verified: boolean;
  romSha256: string;
  // SHA-256 of the generator wheel that built it; a newer generator can
  // build a different wiki from the same ROM.
  generator: string;
  createdAt: string;
}

const DATABASE = "romwiki-local";
const WIKIS = "wikis";
const FILES = "files";

let opening: Promise<IDBDatabase> | undefined;

function database(): Promise<IDBDatabase> {
  opening ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(WIKIS, { keyPath: "id" });
      // Keyed by [wiki id, path] so one wiki's files form a key range.
      request.result.createObjectStore(FILES);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () =>
      reject(new Error("Close other ROM Wiki tabs, then try again."));
  }).catch((error: unknown) => {
    opening = undefined;
    throw error;
  });
  return opening;
}

function finished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () =>
      reject(transaction.error ?? new Error("Saving was interrupted."));
  });
}

function result<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function filesOf(id: string): IDBKeyRange {
  return IDBKeyRange.bound([id, ""], [id, "￿"]);
}

export async function listWikis(): Promise<LocalWiki[]> {
  const db = await database();
  const wikis = await result<LocalWiki[]>(
    db.transaction(WIKIS).objectStore(WIKIS).getAll(),
  );
  return wikis.sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt),
  );
}

export async function saveWiki(
  wiki: LocalWiki,
  files: Map<string, Uint8Array>,
): Promise<void> {
  const db = await database();
  const transaction = db.transaction([WIKIS, FILES], "readwrite");
  const store = transaction.objectStore(FILES);
  store.delete(filesOf(wiki.id));
  for (const [path, data] of files) store.put(data, [wiki.id, path]);
  transaction.objectStore(WIKIS).put(wiki);
  await finished(transaction);
  // Ask the browser not to evict wikis under storage pressure; refusing is
  // fine, as eviction only means generating again.
  await navigator.storage?.persist?.().catch(() => false);
}

export async function readWikiFile(path: string): Promise<Uint8Array> {
  const id = path.split("/", 1)[0];
  const db = await database();
  const data = await result<Uint8Array | undefined>(
    db.transaction(FILES).objectStore(FILES).get([id, path]),
  );
  if (!data)
    throw new Error(
      "This part of the wiki is missing from this browser. Generate it again.",
    );
  return data;
}

export async function readWikiFiles(id: string): Promise<Map<string, Uint8Array>> {
  const db = await database();
  const store = db.transaction(FILES).objectStore(FILES);
  const [keys, values] = await Promise.all([
    result(store.getAllKeys(filesOf(id))),
    result<Uint8Array[]>(store.getAll(filesOf(id))),
  ]);
  return new Map(
    keys.map((key, index) => [(key as [string, string])[1], values[index]]),
  );
}

export async function deleteWiki(id: string): Promise<void> {
  const db = await database();
  const transaction = db.transaction([WIKIS, FILES], "readwrite");
  transaction.objectStore(FILES).delete(filesOf(id));
  transaction.objectStore(WIKIS).delete(id);
  await finished(transaction);
}
