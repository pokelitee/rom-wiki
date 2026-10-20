import { forgetLocalData } from "../data/client";
import { EXPORT_EXTENSION, decodeWiki, encodeWiki } from "./bundle";
import {
  type LocalWiki,
  deleteWiki,
  listWikis,
  readWikiFiles,
  saveWiki,
} from "./store";

export async function storeWiki(
  wiki: LocalWiki,
  files: Map<string, Uint8Array>,
): Promise<void> {
  await saveWiki(wiki, files);
  forgetLocalData(wiki.id);
}

export async function importWiki(file: File): Promise<LocalWiki> {
  const { wiki, files } = await decodeWiki(file);
  await storeWiki(wiki, files);
  return wiki;
}

export async function exportWiki(
  id: string,
): Promise<{ blob: Blob; name: string }> {
  const wiki = (await listWikis()).find((entry) => entry.id === id);
  if (!wiki) throw new Error("This wiki is no longer in this browser.");
  const blob = await encodeWiki(wiki, await readWikiFiles(id));
  return { blob, name: `${fileName(wiki.game.name)}${EXPORT_EXTENSION}` };
}

export async function removeWiki(id: string): Promise<void> {
  await deleteWiki(id);
  forgetLocalData(id);
}

function fileName(name: string): string {
  return (
    name
      .normalize("NFKD")
      .replace(/[^\w\s-]/g, "")
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, "-") || "rom-wiki"
  );
}
