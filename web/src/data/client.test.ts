import { afterEach, expect, it, vi } from "vitest";
import { dataUrl, loadData } from "./client";

afterEach(() => vi.unstubAllGlobals());

it("deduplicates successful resource requests", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ records: [1] }) });
  vi.stubGlobal("fetch", fetcher);
  const [left, right] = await Promise.all([
    loadData("cache-test.json"),
    loadData("cache-test.json"),
  ]);
  expect(left).toEqual(right);
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("allows retrying failed requests", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 503 })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ready: true }) });
  vi.stubGlobal("fetch", fetcher);
  await expect(loadData("retry-test.json")).rejects.toThrow("503");
  await expect(loadData("retry-test.json")).resolves.toEqual({ ready: true });
});

it("keeps requests inside the configured data directory", () => {
  expect(dataUrl("platinum/index.json")).toContain("data/platinum/index.json");
  for (const path of ["../private", "/outside", "https://example.com"])
    expect(() => dataUrl(path)).toThrow();
});
