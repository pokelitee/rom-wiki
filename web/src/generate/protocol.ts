// Messages between the page and the generator worker.

export interface BuildRequest {
  type: "build";
  // The site's `generator/` directory, as an absolute URL.
  runtimeUrl: string;
  rom: File;
  baseRom?: File;
}

export type WorkerMessage =
  | { type: "progress"; message: string }
  | {
      type: "done";
      // `path -> bytes`, as `romwiki.web_build.build_wiki` returns them.
      files: Record<string, Uint8Array>;
      // SHA-256 of the generator wheel that built them.
      generator: string;
    }
  | { type: "error"; message: string };
