import { Download } from "lucide-react";
import type { Game } from "../../data/types";
import { dataUrl } from "../../data/client";
import { countLabel, title } from "../../lib/utils";
import { Button } from "../../components/ui/button";
import { CopyButton } from "../../components/copy-button";
import { SectionIcon } from "../../components/section-icon";

// Download kinds are dataset names; wild encounters publish as encounters.
const SECTION_OF_KIND: Record<string, string> = {
  wild_encounters: "encounters",
};

function size(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.ceil(bytes / 1024)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Downloads({ game }: { game: Game }) {
  return (
    <>
      <p className="eyebrow">Complete normalized datasets</p>
      <h1>Data downloads</h1>
      <p className="lead">
        Deterministic gzip archives with ROM facts, relationships, provenance,
        and labeled reference metadata.
      </p>
      <div className="download-grid">
        {game.downloads.map((entry) => (
          <article className="panel download-card" key={entry.path}>
            <header>
              <span className="download-icon">
                <SectionIcon
                  section={SECTION_OF_KIND[entry.kind] ?? entry.kind}
                  size={18}
                />
              </span>
              <div>
                <h2>{title(entry.kind)}</h2>
                <p className="muted">
                  {countLabel(entry.record_count, "record")} ·{" "}
                  {size(entry.compressed_bytes)} · gzip JSON
                </p>
              </div>
            </header>
            <div className="checksum-row">
              <span className="muted">SHA-256</span>
              <code title={entry.sha256}>{entry.sha256.slice(0, 16)}…</code>
              <CopyButton
                value={entry.sha256}
                label={`Copy the ${title(entry.kind)} SHA-256 checksum`}
              />
            </div>
            <Button asChild variant="outline">
              <a href={dataUrl(`${game.id}/downloads/${entry.path}`)} download>
                <Download size={15} aria-hidden="true" />
                Download
              </a>
            </Button>
          </article>
        ))}
      </div>
    </>
  );
}
