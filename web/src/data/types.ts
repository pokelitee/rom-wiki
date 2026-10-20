export type Json =
  string | number | boolean | null | Json[] | { [key: string]: Json };
export type DataObject = { [key: string]: Json };
export interface IndexRecord {
  id: string;
  label: string;
  search: string;
  fields: Record<string, string | number | string[]>;
  chunk: string;
  sprite?: string;
}
export interface Section {
  index: string;
  metadata: DataObject;
  metadata_path: string;
}
export interface DocumentEntry {
  id: string;
  label: string;
  path: string;
}
export interface DownloadEntry {
  kind: string;
  path: string;
  compressed_bytes: number;
  record_count: number;
  sha256: string;
}
// The Pokémon whose sprite represents a game, or the library as a whole.
export interface Mascot {
  name: string;
  sprite: string;
}
// Present on a wiki generated in this browser.
export interface LocalGameInfo {
  // False when no profile knew the ROM and it was read as the retail game
  // its header names.
  verified: boolean;
  profile: string;
  createdAt: string;
  // Built by an earlier generator than the site serves now.
  outdated: boolean;
}
export interface Game {
  id: string;
  name: string;
  description: string;
  generation: number;
  theme: string;
  mascot?: Mascot | null;
  versions: string[];
  sections: Record<string, Section>;
  comparisons: Record<string, string>;
  downloads: DownloadEntry[];
  documents: DocumentEntry[];
  search_index: string;
  local?: LocalGameInfo;
}
export interface Manifest {
  schema_version: number;
  mascot?: Mascot | null;
  games: Game[];
}
export interface RecordDetail {
  record: DataObject;
  relationships: DataObject;
}
export interface Comparison {
  baseline: string;
  counts: Record<string, number>;
  records: DataObject[];
}
