export interface OutlineEntry {
  id: string;
  text: string;
}

// Anchor IDs for guide headings, shared by the rendered headings and the
// guide's contents list so both always agree.
export function headingSlug(text: string): string {
  return text
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s/g, "-");
}

function plainText(markdown: string): string {
  return markdown
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`~]/g, "")
    .trim();
}

// The guide's second-level headings, outside fenced code blocks.
export function outline(markdown: string): OutlineEntry[] {
  const entries: OutlineEntry[] = [];
  let fenced = false;
  for (const line of markdown.split("\n")) {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    const heading = !fenced && /^##\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      const text = plainText(heading[1]);
      entries.push({ id: headingSlug(text), text });
    }
  }
  return entries;
}
