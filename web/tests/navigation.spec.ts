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
      // Types list as tiles; every other section lists as a table.
      const list = section === "types" ? ".type-grid" : ".catalog-table";
      await expect(page.locator(list)).toBeVisible();
      const first = page.locator(`${list} a`).first();
      if (await first.count()) {
        await first.click();
        await expect(page.locator(".record-hero h1")).toBeVisible();
      }
      // Records in one section vary in shape, so also render the middle
      // and last records rather than only the first.
      const index = JSON.parse(
        await readFile(
          new URL(
            `../public/data/${game.sections[section].index}`,
            import.meta.url,
          ),
          "utf8",
        ),
      ) as { records: { id: string }[] };
      const ids = index.records.map((record) => record.id);
      for (const id of new Set([ids[Math.floor(ids.length / 2)], ids.at(-1)])) {
        if (!id) continue;
        await page.goto(`./#/${game.id}/${section}/${id}`);
        await expect(page.locator(".record-hero h1")).toBeVisible();
      }
    }
    await page.goto(`./#/${game.id}/docs/data-sources`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Data sources" }),
    ).toBeVisible();
    await expect(page.locator("article")).not.toBeEmpty();
    await page.goto(`./#/${game.id}/downloads`);
    await expect(
      page.getByRole("heading", { name: "Data downloads" }),
    ).toBeVisible();
    if (Object.keys(game.comparisons).length) {
      await page.goto(`./#/${game.id}/changes`);
      await expect(
        page.getByRole("group", { name: "Show changes" }),
      ).toBeVisible();
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
  // Every request fails until Retry, since the catalog and the sprite
  // lookup both ask for this index and either may ask first.
  let retried = false;
  await page.route("**/data/platinum/pokemon/index-*.json", async (route) => {
    if (retried) await route.continue();
    else await route.fulfill({ status: 503, body: "Unavailable" });
  });
  await page.goto("./#/platinum/pokemon");
  await expect(page.getByRole("alert")).toContainText("503");
  retried = true;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".catalog-table")).toBeVisible();
});

test("record icons recover from a failed index without a reload", async ({
  page,
}) => {
  const platinum = manifest.games.find((game) => game.id === "platinum");
  const readIndex = async (section: string) =>
    platinum?.sections[section]
      ? (JSON.parse(
          await readFile(
            new URL(
              `../public/data/${platinum.sections[section].index}`,
              import.meta.url,
            ),
            "utf8",
          ),
        ) as { records: { id: string; sprite?: string }[] })
      : { records: [] };
  const [abilities, pokemon] = await Promise.all([
    readIndex("abilities"),
    readIndex("pokemon"),
  ]);
  test.skip(
    !abilities.records.length ||
      !pokemon.records.some((record) => record.sprite),
    "needs Platinum abilities and Pokémon sprites",
  );
  // Ability pages link Pokémon without loading their index themselves, so
  // only the icon lookup sees the failures.
  let failures = 0;
  await page.route("**/data/platinum/pokemon/index-*.json", async (route) => {
    if (failures < 2) {
      failures++;
      await route.fulfill({ status: 503, body: "Unavailable" });
    } else await route.continue();
  });
  await page.goto(`./#/platinum/abilities/${abilities.records[0].id}`);
  await expect(
    page.locator(".detail-section .entity-icon").first(),
  ).toBeVisible({ timeout: 10_000 });
  expect(failures).toBe(2);
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
