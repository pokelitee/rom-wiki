import type { Game } from "../data/types";
import type { LocalWiki } from "./store";

// A generated wiki saved as one file, so it can move to another browser.
const FORMAT = "romwiki-local-wiki";
const VERSION = 1;
export const LOCAL_ID = /^local-[0-9a-f]{12}$/;
export const EXPORT_EXTENSION = ".romwiki.json.gz";

interface ExportFile {
  format: typeof FORMAT;
  version: typeof VERSION;
  wiki: LocalWiki;
  files: Record<string, string>;
}

interface GeneratedManifest {
  games: Game[];
  local: {
    profile: string;
    verified: boolean;
    rom_sha256: string;
  };
}

/** The library entry and stored files for a bundle `build_wiki` returned. */
export function wikiFromBundle(
  bundle: Map<string, Uint8Array>,
  generator: string,
  createdAt = new Date().toISOString(),
): { wiki: LocalWiki; files: Map<string, Uint8Array> } {
  const manifestBytes = bundle.get("manifest.json");
  if (!manifestBytes) throw new Error("The generator returned no manifest.");
  const manifest = JSON.parse(
    new TextDecoder().decode(manifestBytes),
  ) as GeneratedManifest;
  const [game] = manifest.games;
  const files = new Map(
    [...bundle].filter(([path]) => path !== "manifest.json"),
  );
  const wiki: LocalWiki = {
    id: game.id,
    game,
    profile: manifest.local.profile,
    verified: manifest.local.verified,
    romSha256: manifest.local.rom_sha256,
    generator,
    createdAt,
  };
  checkWiki(wiki, files);
  return { wiki, files };
}

export async function encodeWiki(
  wiki: LocalWiki,
  files: Map<string, Uint8Array>,
): Promise<Blob> {
  const value: ExportFile = {
    format: FORMAT,
    version: VERSION,
    wiki,
    files: Object.fromEntries(
      [...files].map(([path, data]) => [path, toBase64(data)]),
    ),
  };
  const stream = new Blob([JSON.stringify(value)])
    .stream()
    .pipeThrough(new CompressionStream("gzip"));
  return new Response(stream, {
    headers: { "Content-Type": "application/gzip" },
  }).blob();
}

export async function decodeWiki(
  file: Blob,
): Promise<{ wiki: LocalWiki; files: Map<string, Uint8Array> }> {
  let value: ExportFile;
  try {
    const stream = file.stream().pipeThrough(new DecompressionStream("gzip"));
    value = JSON.parse(await new Response(stream).text()) as ExportFile;
  } catch {
    throw new Error("This file is not a ROM Wiki export.");
  }
  if (value?.format !== FORMAT || typeof value.files !== "object")
    throw new Error("This file is not a ROM Wiki export.");
  if (value.version !== VERSION)
    throw new Error("This export comes from a newer version of ROM Wiki.");
  const files = new Map(
    Object.entries(value.files).map(([path, data]) => [path, fromBase64(data)]),
  );
  checkWiki(value.wiki, files);
  return { wiki: value.wiki, files };
}

// A wiki's files can only live under its own ID, so neither a generated nor
// an imported wiki can shadow another wiki's or the published data.
function checkWiki(wiki: LocalWiki, files: Map<string, Uint8Array>) {
  if (
    typeof wiki?.id !== "string" ||
    !LOCAL_ID.test(wiki.id) ||
    wiki.game?.id !== wiki.id ||
    typeof wiki.game.name !== "string" ||
    typeof wiki.game.sections !== "object"
  )
    throw new Error("This wiki is not a locally generated ROM Wiki.");
  for (const path of files.keys())
    if (!path.startsWith(`${wiki.id}/`) || path.split("/").includes(".."))
      throw new Error("This wiki contains files outside itself.");
}

function toBase64(data: Uint8Array): string {
  let text = "";
  for (let start = 0; start < data.length; start += 0x8000)
    text += String.fromCharCode(...data.subarray(start, start + 0x8000));
  return btoa(text);
}

function fromBase64(value: string): Uint8Array {
  const text = atob(value);
  const data = new Uint8Array(text.length);
  for (let index = 0; index < text.length; index++)
    data[index] = text.charCodeAt(index);
  return data;
}
