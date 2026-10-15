import type { Game } from "../../data/types";
import { dataUrl } from "../../data/client";
import { title } from "../../lib/utils";

export function Downloads({ game }: { game: Game }) {
  return (
    <>
      <p className="eyebrow">Complete normalized datasets</p>
      <h1>Data downloads</h1>
      <p className="lead">
        Deterministic gzip archives with ROM facts, relationships, provenance,
        and labeled reference metadata.
      </p>
      <div className="panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>Dataset</th>
              <th>Records</th>
              <th>Size</th>
              <th>Download</th>
            </tr>
          </thead>
          <tbody>
            {game.downloads.map((entry) => (
              <tr key={entry.path}>
                <td>
                  {title(entry.kind)}
                  <details>
                    <summary>SHA-256</summary>
                    <code className="checksum">{entry.sha256}</code>
                  </details>
                </td>
                <td>{entry.record_count.toLocaleString()}</td>
                <td>{Math.ceil(entry.compressed_bytes / 1024)} KB</td>
                <td>
                  <a
                    href={dataUrl(`${game.id}/downloads/${entry.path}`)}
                    download
                  >
                    JSON.gz ↓
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
