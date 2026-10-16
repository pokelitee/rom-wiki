import { expect, it } from "vitest";
import { headingSlug, outline } from "./outline";

it("lists second-level headings outside code fences with matching anchors", () => {
  expect(
    outline(
      [
        "# Title",
        "## Primary ROM",
        "```",
        "## not a heading",
        "```",
        "## [Patching](patching.md) notes",
        "### Deeper",
        "## Bugs & fixes",
      ].join("\n"),
    ),
  ).toEqual([
    { id: "primary-rom", text: "Primary ROM" },
    { id: "patching-notes", text: "Patching notes" },
    { id: "bugs--fixes", text: "Bugs & fixes" },
  ]);
  expect(headingSlug("Bugs & fixes")).toBe("bugs--fixes");
});
