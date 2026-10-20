// Runs `romwiki.web_build.build_wiki` in Pyodide, off the page's thread.
import type { BuildRequest, WorkerMessage } from "./protocol";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";

interface PyProxy {
  toJs(options: { dict_converter: typeof Object.fromEntries }): unknown;
  destroy(): void;
}

interface Pyodide {
  FS: {
    mkdirTree(path: string): void;
    writeFile(path: string, data: Uint8Array): void;
    mount(type: unknown, options: { files: File[] }, path: string): void;
    unmount(path: string): void;
    filesystems: { WORKERFS: unknown };
  };
  globals: { set(name: string, value: unknown): void };
  runPython(code: string): unknown;
  unpackArchive(
    buffer: Uint8Array,
    format: string,
    options: { extractDir: string },
  ): void;
}

interface RuntimeEntry {
  path: string;
  sha256: string;
}

interface RuntimeManifest {
  wheel: RuntimeEntry;
  resources: RuntimeEntry;
  pokedb: Record<string, RuntimeEntry>;
}

const scope = self as unknown as {
  onmessage: ((event: MessageEvent<BuildRequest>) => void) | null;
  postMessage(message: WorkerMessage, transfer?: Transferable[]): void;
};

function post(message: WorkerMessage, transfer: Transferable[] = []) {
  scope.postMessage(message, transfer);
}

const progress = (message: string) => post({ type: "progress", message });

let runtime: Promise<{ pyodide: Pyodide; generator: string }> | undefined;
let builds = 0;

scope.onmessage = async ({ data }) => {
  try {
    runtime ??= start(data.runtimeUrl).catch((error: unknown) => {
      runtime = undefined;
      throw error;
    });
    const { pyodide, generator } = await runtime;
    const files = build(pyodide, data);
    // Each file is a copy out of the runtime, so its buffer can move to the
    // page instead of being copied again.
    const buffers = new Set(
      Object.values(files).map((file) => file.buffer as ArrayBuffer),
    );
    post({ type: "done", files, generator }, [...buffers]);
  } catch (error) {
    post({ type: "error", message: errorMessage(error) });
  }
};

async function start(runtimeUrl: string) {
  progress("Loading the Python runtime…");
  const { loadPyodide } = (await import(
    /* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`
  )) as { loadPyodide(options: { indexURL: string }): Promise<Pyodide> };
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  progress("Installing the wiki generator…");
  const manifest = (await (
    await fetchOk(new URL("manifest.json", runtimeUrl))
  ).json()) as RuntimeManifest;
  const download = async (entry: RuntimeEntry) => {
    const data = new Uint8Array(
      await (await fetchOk(new URL(entry.path, runtimeUrl))).arrayBuffer(),
    );
    if ((await sha256(data)) !== entry.sha256)
      throw new Error("A generator download was corrupted. Please retry.");
    return data;
  };
  const sitePackages = pyodide.runPython(
    "import site; site.getsitepackages()[0]",
  ) as string;
  pyodide.unpackArchive(await download(manifest.wheel), "zip", {
    extractDir: sitePackages,
  });
  pyodide.unpackArchive(await download(manifest.resources), "zip", {
    extractDir: "/repo",
  });
  pyodide.FS.mkdirTree("/pokedb");
  for (const [generation, entry] of Object.entries(manifest.pokedb))
    pyodide.FS.writeFile(
      `/pokedb/gen${generation}.json.gz`,
      await download(entry),
    );
  pyodide.globals.set("report_progress", progress);
  pyodide.runPython(PREPARE);
  return { pyodide, generator: manifest.wheel.sha256 };
}

function build(pyodide: Pyodide, request: BuildRequest) {
  // WORKERFS reads the files on demand, so a large DS ROM is never copied
  // into the runtime's memory.
  const directory = `/roms/${++builds}`;
  pyodide.FS.mkdirTree(directory);
  const roms = [request.rom, ...(request.baseRom ? [request.baseRom] : [])];
  pyodide.FS.mount(pyodide.FS.filesystems.WORKERFS, { files: roms }, directory);
  try {
    progress("Reading your ROM…");
    pyodide.globals.set("rom_path", `${directory}/${request.rom.name}`);
    pyodide.globals.set(
      "base_rom_path",
      request.baseRom ? `${directory}/${request.baseRom.name}` : null,
    );
    const result = pyodide.runPython(BUILD) as PyProxy;
    try {
      return result.toJs({ dict_converter: Object.fromEntries }) as Record<
        string,
        Uint8Array
      >;
    } finally {
      result.destroy();
    }
  } finally {
    pyodide.FS.unmount(directory);
  }
}

const PREPARE = `
import logging

class _Progress(logging.Handler):
    def emit(self, record):
        report_progress(record.getMessage())

logging.getLogger().addHandler(_Progress())
logging.getLogger().setLevel(logging.INFO)
`;

const BUILD = `
from pathlib import Path
from romwiki.sources import PokeDBGeneration
from romwiki.web_build import build_wiki

build_wiki(
    Path(rom_path),
    root=Path("/repo"),
    pokedb=lambda generation: PokeDBGeneration.load_pack(
        Path(f"/pokedb/gen{generation}.json.gz").read_bytes()
    ),
    base_rom=Path(base_rom_path) if base_rom_path else None,
    id_prefix="local-",
)
`;

async function fetchOk(url: URL): Promise<Response> {
  const response = await fetch(url);
  if (!response.ok)
    throw new Error(
      `Could not download the generator (${response.status}). Please retry.`,
    );
  return response;
}

async function sha256(data: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data as BufferSource);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

// A Python exception arrives with its whole traceback; its last line is the
// error the pipeline raised, which is what the reader needs.
function errorMessage(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  const lines = text.trim().split("\n");
  const last = lines[lines.length - 1] ?? text;
  return last.replace(/^[\w.]+(Error|Exception): /, "");
}
