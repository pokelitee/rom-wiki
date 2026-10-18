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
  await expect(page.locator(".evolution-step").first()).toContainText(
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

test("type pages list their Pokémon", async ({ page }) => {
  test.skip(!platinum?.sections.types, "needs the Platinum type chart");
  await page.goto("./#/platinum/types/fire");
  const pokemon = page.locator("#section-pokemon");
  await expect(pokemon.getByRole("link", { name: "Charmander" })).toBeVisible();
  await expect(pokemon.getByRole("link", { name: "Bulbasaur" })).toHaveCount(0);
  await pokemon.getByRole("link", { name: "Charmander" }).click();
  await expect(page.locator(".record-hero h1")).toHaveText("Charmander");
});

test("parts a record lacks leave no extra space", async ({ page }) => {
  test.skip(!platinum?.sections.trainers, "needs Platinum trainers");
  // Trainers have no sprite, description, version picker, or reference data.
  const trainers = await readData<{ records: { id: string }[] }>(
    platinum.sections.trainers.index,
  );
  await page.goto(`./#/platinum/trainers/${trainers.records[0].id}`);
  await expect(
    page.locator(".record-page > .detail-section").first(),
  ).toBeVisible();
  const gaps = await page.locator(".record-page").evaluate((root) => {
    const parts = [...root.children].filter(
      (part) => part.getBoundingClientRect().height > 0,
    );
    return parts
      .slice(1)
      .map((part, index) =>
        Math.round(
          part.getBoundingClientRect().top -
            parts[index].getBoundingClientRect().bottom,
        ),
      );
  });
  expect(new Set(gaps).size).toBe(1);
});

test("evolution trees show the whole family from any stage", async ({
  page,
}) => {
  const pokemon = platinum?.sections.pokemon
    ? await readData<{ records: { id: string }[] }>(
        platinum.sections.pokemon.index,
      )
    : { records: [] };
  test.skip(
    !pokemon.records.some((record) => record.id === "beautifly"),
    "needs Platinum's Wurmple family",
  );
  await page.goto("./#/platinum/pokemon/beautifly");
  const tree = page.locator("#section-evolutions .evolution-tree");
  for (const name of ["Wurmple", "Silcoon", "Beautifly", "Cascoon", "Dustox"])
    await expect(tree.getByRole("link", { name })).toBeVisible();
  await expect(tree.locator('[aria-current="page"]')).toHaveText("Beautifly");
});

test("a Pokémon's wild encounters merge seasons and versions", async ({
  page,
}) => {
  test.skip(
    !manifest.games.some((game) => game.id === "black-2-white-2"),
    "needs Black 2 & White 2",
  );
  await page.goto("./#/black-2-white-2/pokemon/deerling");
  const table = page.locator("#section-wild_encounters table");
  // Four seasons in two versions collapse into one row per encounter.
  await expect(table.locator("tbody tr")).toHaveCount(4);
  await table.getByRole("link", { name: "Route 6" }).click();
  await expect(page.locator(".record-hero h1")).toHaveText("Route 6");
});

test("the header and browser tab show the game's mascot", async ({ page }) => {
  test.skip(!platinum?.mascot, "needs a Platinum mascot");
  await page.goto("./#/platinum");
  await expect(page.locator(".brand-mark img")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.querySelector<HTMLLinkElement>('link[rel="icon"]')?.href,
      ),
    )
    .toMatch(/^data:image\/png/);
});

test("type pages list their moves", async ({ page }) => {
  const moves = platinum?.sections.moves
    ? await readData<{ records: { id: string }[] }>(
        platinum.sections.moves.index,
      )
    : { records: [] };
  test.skip(
    !moves.records.some((record) => record.id === "ember") ||
      !platinum?.sections.types,
    "needs Platinum's Fire moves",
  );
  await page.goto("./#/platinum/types/fire");
  const section = page.locator("#section-moves");
  await expect(section.getByRole("link", { name: "Ember" })).toBeVisible();
  await expect(section.getByRole("link", { name: "Tackle" })).toHaveCount(0);
});

test("pages leave out facts that say nothing", async ({ page }) => {
  const hgss = manifest.games.find(
    (game) => game.id === "heart-gold-soul-silver",
  );
  test.skip(!hgss, "needs HeartGold & SoulSilver");
  await page.goto("./#/heart-gold-soul-silver/encounters/area-000");
  // Swarm and night fishing Pokémon read as one encounter table.
  await expect(
    page.locator("#section-special table").getByText("Fishing swarm"),
  ).toBeVisible();
  // Every area is active and in both versions; neither is worth a fact.
  await expect(page.locator("#section-versions")).toHaveCount(0);
  await expect(page.locator("#section-overview")).toHaveCount(0);
  await page.goto("./#/heart-gold-soul-silver/pokemon/pidgey");
  await expect(page.locator("#section-wild_encounters")).toBeVisible();
  await expect(page.locator("#section-versions")).toHaveCount(0);
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

const trainerIndex = platinum.sections.trainers
  ? await readData<{ records: { id: string; label: string }[] }>(
      platinum.sections.trainers.index,
    )
  : { records: [] };
const sharedTrainer = trainerIndex.records.find(
  (record, index, records) =>
    records.findIndex((other) => other.label === record.label) !== index,
);

test("records that share a name are told apart and linked", async ({
  page,
}) => {
  test.skip(!sharedTrainer, "No two published trainers share a name");
  const label = sharedTrainer!.label;
  await page.goto(`./#/platinum/search?q=${encodeURIComponent(label)}`);
  const result = page.locator(".search-results a", { hasText: label }).first();
  await expect(result.locator(".result-context")).toContainText("#");
  await page.goto(`./#/platinum/trainers/${sharedTrainer!.id}`);
  const others = page.locator("#section-same-name");
  await expect(
    others.getByRole("heading", { name: `Also named ${label}` }),
  ).toBeVisible();
  await expect(others.locator("a").first()).toContainText(label);
});
