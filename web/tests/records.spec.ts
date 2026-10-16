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
  const headers = await page.locator("main table th").allTextContents();
  expect(headers.map((header) => header.trim().toLowerCase())).not.toContain(
    "id",
  );
  await page.getByText("Sources and record details").click();
  await page.getByText("Full record", { exact: true }).click();
  await expect(page.locator(".raw-record pre")).toContainText('"gender_ratio"');
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
