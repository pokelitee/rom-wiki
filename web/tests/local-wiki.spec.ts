import { expect, test } from "@playwright/test";
import { readFile, readdir } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import type { Manifest } from "../src/data/types";

// CI has no ROMs, so this builds the file a wiki export would be from the
// published Platinum wiki, renamed to a local ID, and imports it.
const LOCAL_ID = "local-0123456789ab";
const DATA = new URL("../public/data/", import.meta.url);

async function platinumExport(): Promise<Buffer> {
  const manifest = JSON.parse(
    await readFile(new URL("manifest.json", DATA), "utf8"),
  ) as Manifest;
  const game = manifest.games.find((entry) => entry.id === "platinum");
  if (!game) throw new Error("The published data has no Platinum wiki");
  const rename = (text: string) =>
    text.replaceAll('"platinum/', `"${LOCAL_ID}/`);
  const files: Record<string, string> = {};
  const root = new URL("platinum/", DATA);
  for (const name of await readdir(root, { recursive: true })) {
    const path = name.replaceAll("\\", "/");
    if (!path.includes(".")) continue;
    const data = await readFile(new URL(path, root));
    files[`${LOCAL_ID}/${path}`] = (
      path.endsWith(".json") ? Buffer.from(rename(data.toString("utf8"))) : data
    ).toString("base64");
  }
  const wiki = {
    id: LOCAL_ID,
    game: JSON.parse(rename(JSON.stringify({ ...game, id: LOCAL_ID }))),
    profile: "platinum-us",
    verified: false,
    romSha256: "0123456789ab".padEnd(64, "0"),
    generator: "test",
    createdAt: "2026-10-20T00:00:00.000Z",
  };
  return gzipSync(
    JSON.stringify({ format: "romwiki-local-wiki", version: 1, wiki, files }),
  );
}

test("an exported wiki imports, browses, and deletes", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./#/");
  await page.getByRole("link", { name: "Make a wiki from your ROM" }).click();
  await expect(
    page.getByRole("heading", { name: "Make a wiki", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Wiki file").setInputFiles({
    name: "platinum.romwiki.json.gz",
    mimeType: "application/gzip",
    buffer: await platinumExport(),
  });
  await expect(page.getByRole("status")).toContainText(
    "Pokémon Platinum is ready",
  );

  await page.getByRole("link", { name: "Open the wiki" }).click();
  await expect(page).toHaveURL(new RegExp(`#/${LOCAL_ID}$`));
  await expect(page.getByText("Made in this browser from your ROM")).toBeVisible();
  await expect(page.getByText("read as the game its header names")).toBeVisible();
  await page.goto(`./#/${LOCAL_ID}/pokemon`);
  await page.getByRole("textbox", { name: "Search pokemon" }).fill("bulbasaur");
  await page.getByRole("link", { name: "Bulbasaur", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Base stats" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Base stats" })).toBeVisible();

  await page.goto("./#/");
  await expect(page.getByRole("heading", { name: "Your wikis" })).toBeVisible();
  await expect(page.getByText("Unverified")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete Platinum" }).click();
  await expect(page.getByRole("heading", { name: "Your wikis" })).toHaveCount(0);
  await page.goto(`./#/${LOCAL_ID}`);
  await expect(
    page.getByRole("heading", { name: "Page not found" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("a file that is not an export is rejected", async ({ page }) => {
  await page.goto("./#/make");
  await page.getByLabel("Wiki file").setInputFiles({
    name: "not-a-wiki.json.gz",
    mimeType: "application/gzip",
    buffer: gzipSync("{}"),
  });
  await expect(page.getByRole("alert")).toContainText(
    "not a ROM Wiki export",
  );
});
