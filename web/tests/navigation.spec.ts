import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { Manifest } from "../src/data/types";

const manifest = JSON.parse(
  await readFile(
    new URL("../public/data/manifest.json", import.meta.url),
    "utf8",
  ),
) as Manifest;

test("library, direct links, filtering, refresh, and browser history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("./#/");
  await expect(
    page.getByRole("heading", { name: "Your games. The exact details." }),
  ).toBeVisible();
  await page.goto("./#/platinum/pokemon");
  await page.getByRole("textbox", { name: "Search pokemon" }).fill("bulbasaur");
  await page.getByRole("link", { name: "Bulbasaur", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Bulbasaur", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Base stats" })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Bulbasaur", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("textbox", { name: "Search pokemon" }),
  ).toHaveValue("bulbasaur");
  expect(errors).toEqual([]);
});

test("missing records and unknown games recover to the library", async ({
  page,
}) => {
  await page.goto("./#/platinum/pokemon/does-not-exist");
  await expect(
    page.getByRole("heading", { name: "Record not found" }),
  ).toBeVisible();
  await page.goto("./#/unknown-game");
  await expect(
    page.getByRole("heading", { name: "Page not found" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to the game library" }).click();
  await expect(
    page.getByRole("heading", { name: "Your games. The exact details." }),
  ).toBeVisible();
});

for (const game of manifest.games) {
  test(`${game.id}: all published sections, guides, and downloads load`, async ({
    page,
  }) => {
    const failures: string[] = [];
    page.on("pageerror", (error) => failures.push(error.message));
    for (const section of Object.keys(game.sections)) {
      await page.goto(`./#/${game.id}/${section}`);
      await expect(page.locator(".catalog-table")).toBeVisible();
      const first = page.locator(".catalog-table tbody a").first();
      if (await first.count()) {
        await first.click();
        await expect(page.locator(".record-hero h1")).toBeVisible();
      }
    }
    await page.goto(`./#/${game.id}/docs/data-sources`);
    await expect(page.locator("article")).toContainText("Data sources");
    await page.goto(`./#/${game.id}/downloads`);
    await expect(
      page.getByRole("heading", { name: "Data downloads" }),
    ).toBeVisible();
    if (Object.keys(game.comparisons).length) {
      await page.goto(`./#/${game.id}/changes`);
      await expect(page.locator(".summary-grid")).toBeVisible();
    }
    expect(failures).toEqual([]);
  });
}

test("detail requests stay within the selected game and use chunks", async ({
  page,
}) => {
  const urls: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/data/")) urls.push(request.url());
  });
  await page.goto("./#/platinum/pokemon/bulbasaur");
  await expect(page.locator(".record-hero h1")).toHaveText("Bulbasaur");
  expect(urls.some((url) => /pokemon\/chunk-/.test(url))).toBeTruthy();
  expect(
    urls.every(
      (url) => url.endsWith("manifest.json") || url.includes("/data/platinum/"),
    ),
  ).toBeTruthy();
  expect(urls.some((url) => url.endsWith(".gz"))).toBeFalsy();
});

test("a failed index request offers a working retry", async ({ page }) => {
  let failed = false;
  await page.route("**/data/platinum/pokemon/index-*.json", async (route) => {
    if (!failed) {
      failed = true;
      await route.fulfill({ status: 503, body: "Unavailable" });
    } else await route.continue();
  });
  await page.goto("./#/platinum/pokemon");
  await expect(page.getByRole("alert")).toContainText("503");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".catalog-table")).toBeVisible();
});

test("guide anchors keep the route and reference links reach catalogs", async ({
  page,
}) => {
  await page.route("**/data/platinum/docs/data-sources-*.json", (route) =>
    route.fulfill({
      json: {
        markdown:
          "# Data sources\n\n[Limits](#limits)\n\n[Pokemon](pokemon/index.md)\n\n## Limits\n\nKnown limitations.",
      },
    }),
  );
  await page.goto("./#/platinum/docs/data-sources");
  await page.getByRole("link", { name: "Limits", exact: true }).click();
  await expect(page).toHaveURL(/#\/platinum\/docs\/data-sources$/);
  await expect(
    page.getByRole("heading", { name: "Limits", exact: true }),
  ).toBeVisible();
  await page
    .locator("article")
    .getByRole("link", { name: "Pokemon", exact: true })
    .click();
  await expect(page.locator(".catalog-table")).toBeVisible();
});
