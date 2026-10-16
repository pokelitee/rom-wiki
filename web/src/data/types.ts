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
export interface Game {
  id: string;
  name: string;
  description: string;
  generation: number;
  theme: string;
  versions: string[];
  sections: Record<string, Section>;
  comparisons: Record<string, string>;
  downloads: DownloadEntry[];
  documents: DocumentEntry[];
  search_index: string;
}
export interface Manifest {
  schema_version: number;
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
