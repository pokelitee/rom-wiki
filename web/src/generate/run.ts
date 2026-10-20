import type { BuildRequest, WorkerMessage } from "./protocol";

let worker: Worker | undefined;

/**
 * Build a wiki from `rom` in the generator worker. Pyodide and the generator
 * stay loaded between builds while the page is open.
 */
export function generateWiki(
  rom: File,
  baseRom: File | undefined,
  onProgress: (message: string) => void,
): Promise<{ files: Map<string, Uint8Array>; generator: string }> {
  worker ??= new Worker(new URL("./worker.ts", import.meta.url), {
    type: "module",
  });
  const active = worker;
  return new Promise((resolve, reject) => {
    active.onmessage = ({ data }: MessageEvent<WorkerMessage>) => {
      if (data.type === "progress") onProgress(data.message);
      else if (data.type === "error") reject(new Error(data.message));
      else
        resolve({
          files: new Map(Object.entries(data.files)),
          generator: data.generator,
        });
    };
    active.onerror = (event) => {
      // A crashed worker can't be reused.
      worker = undefined;
      reject(new Error(event.message || "The generator stopped unexpectedly."));
    };
    const request: BuildRequest = {
      type: "build",
      runtimeUrl: new URL(
        `${import.meta.env.BASE_URL}generator/`,
        location.href,
      ).href,
      rom,
      baseRom,
    };
    active.postMessage(request);
  });
}
