import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { Manifest } from "../src/data/types";

const readData = async <T>(path: string): Promise<T> =>
  JSON.parse(
    await readFile(new URL(`../public/data/${path}`, import.meta.url), "utf8"),
  ) as T;

const manifest = await readData<Manifest>("manifest.json");
const platinum = manifest.games.find((game) => game.id === "platinum")!;

test("game search finds records and guides and reports misses", async ({
  page,
}) => {
  await page.goto("./#/platinum/search");
  const box = page.getByRole("textbox", { name: "Search this game" });
  const results = page.locator(".search-results a");

  await box.fill("bulbasaur");
  await results
    .filter({ has: page.getByText("Bulbasaur", { exact: true }) })
    .first()
    .click();
  await expect(page.locator(".record-hero h1")).toHaveText("Bulbasaur");
  await page.goBack();
  await expect(box).toHaveValue("bulbasaur");

  await box.fill("data sources");
  await expect(
    results.filter({ has: page.getByText("Data sources", { exact: true }) }),
  ).not.toHaveCount(0);

  await box.fill("zzzz-no-such-record");
  await expect(page.locator(".results-line")).toHaveText("0 results");
  await expect(
    page.getByText("No records or guides match your search."),
  ).toBeVisible();
});

test("a failed search index request offers a working retry", async ({
  page,
}) => {
  let failed = false;
  await page.route("**/data/platinum/guide-search-*.json", async (route) => {
    if (!failed) {
      failed = true;
      await route.fulfill({ status: 503, body: "Unavailable" });
    } else await route.continue();
  });
  await page.goto("./#/platinum/search?q=bulbasaur");
  await expect(page.getByRole("alert")).toContainText("503");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".results-line")).toBeVisible();
});

test("entity links on a record resolve to published records", async ({
  page,
}) => {
  await page.goto("./#/platinum/pokemon/bulbasaur");
  await expect(page.locator(".record-hero h1")).toHaveText("Bulbasaur");
  const hrefs = await page
    .locator("main a[href^='#/platinum/']")
    .evaluateAll((links) => links.map((link) => link.getAttribute("href")!));
  const targets = [
    ...new Set(
      hrefs.flatMap((href) => {
        const match = /^#\/platinum\/([^/]+)\/([^/?]+)$/.exec(href);
        return match && match[1] in platinum.sections
          ? [`${match[1]}/${match[2]}`]
          : [];
      }),
    ),
  ].map((target) => target.split("/") as [string, string]);
  const linkedSections = new Set(targets.map(([section]) => section));
  expect(linkedSections).toContain("abilities");
  expect(linkedSections).toContain("moves");
  expect(linkedSections).toContain("pokemon");

  const ids = new Map<string, Set<string>>();
  for (const section of linkedSections) {
    const index = await readData<{ records: { id: string }[] }>(
      platinum.sections[section].index,
    );
    ids.set(section, new Set(index.records.map((record) => record.id)));
  }
  const unresolved = targets
    .filter(([section, id]) => !ids.get(section)!.has(id))
    .map(([section, id]) => `${section}/${id}`);
  expect(unresolved).toEqual([]);

  await page.getByRole("link", { name: "Overgrow", exact: true }).click();
  await expect(page.locator(".record-hero h1")).toHaveText("Overgrow");
});

test("record pages show readable values and keep raw data in the details", async ({
  page,
}) => {
  await page.goto("./#/platinum/pokemon/bulbasaur");
  await expect(page.locator(".record-hero h1")).toHaveText("Bulbasaur");
  await expect(page.getByText("87.5% male")).toBeVisible();
  await expect(page.locator(".stat-row span").first()).toHaveText("HP");
  await expect(page.locator(".evolution-list li").first()).toContainText(
    "Level 16",
  );
  const headers = await page.locator("main table th").allTextContents();
  expect(headers.map((header) => header.trim().toLowerCase())).not.toContain(
    "id",
  );
  await page.getByText("Sources and record details").click();
  await page.getByText("Full record", { exact: true }).click();
  await expect(page.locator(".raw-record pre")).toContainText('"gender_ratio"');
});

test("trainer parties render as cards", async ({ page }) => {
  await page.goto("./#/platinum/trainers?q=roark");
  await page.locator(".catalog-table tbody a").first().click();
  await expect(page.locator(".record-hero h1")).toContainText("Roark");
  const card = page.locator(".party-card").first();
  await expect(card).toContainText("Level");
  await expect(card.locator(".party-moves tbody tr").first()).toBeVisible();
  await expect(page.getByText("Calculated stats")).toHaveCount(0);
  // Roark carries two Potions, shown once with a count.
  const items = page.locator("#section-ai_battle_items");
  await expect(items.locator(".chip-list > *")).toHaveCount(1);
  await expect(items).toContainText("Potion×2");
});

test("encounter pages lead with real encounters and hide empty methods", async ({
  page,
}) => {
  await page.goto("./#/platinum/encounters?q=route%20201");
  await page.locator(".catalog-table tbody a").first().click();
  await expect(page.locator(".record-hero h1")).toHaveText("Route 201");
  const headings = await page.locator("main section h2").allTextContents();
  expect(headings[0] === "Overview" ? headings[1] : headings[0]).toBe(
    "Walking",
  );
  expect(headings).not.toContain("Good rod");
  await expect(page.locator("main table .entity-link").first()).toBeVisible();
});

const comparative = manifest.games.find(
  (game) => Object.keys(game.comparisons).length,
);

test("changes summarize each record and filter by status", async ({ page }) => {
  test.skip(!comparative, "No published game has comparisons");
  await page.goto(`./#/${comparative!.id}/changes`);
  await expect(page.locator(".change-summary").first()).not.toBeEmpty();
  await page
    .getByRole("group", { name: "Show changes" })
    .getByRole("button", { name: /^Changed/ })
    .click();
  await expect(page).toHaveURL(/status=changed/);
  const badges = await page
    .locator(".change-record > summary > .badge")
    .allTextContents();
  expect(new Set(badges)).toEqual(new Set(["Changed"]));
});

test("the game picker switches games from a styled menu", async ({ page }) => {
  await page.goto("./#/platinum");
  await page.getByLabel("Choose a game").click();
  await expect(
    page.getByRole("option", { name: "Platinum", exact: true }),
  ).toBeVisible();
  await page.getByRole("option", { name: "Game library" }).click();
  await expect(
    page.getByRole("heading", { name: "Your games. The exact details." }),
  ).toBeVisible();
});

test("downloads offer copyable checksums and download buttons", async ({
  page,
}) => {
  await page.goto("./#/platinum/downloads");
  const card = page.locator(".download-card").first();
  await expect(card.getByRole("link", { name: "Download" })).toHaveAttribute(
    "href",
    /downloads\/.+\.json\.gz$/,
  );
  await expect(card.getByRole("button", { name: /SHA-256/ })).toBeVisible();
});

test("mobile navigation opens, navigates, and closes", async ({
  page,
  isMobile,
}) => {
  test.skip(!isMobile, "The navigation toggle is only shown on small screens");
  await page.goto("./#/platinum");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("button", { name: "Close navigation" }),
  ).toHaveAttribute("aria-expanded", "true");
  await page
    .getByRole("navigation", { name: "Game navigation" })
    .getByRole("link", { name: "Search this game" })
    .click();
  await expect(page).toHaveURL(/#\/platinum\/search$/);
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toHaveAttribute("aria-expanded", "false");
});
