import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BookOpen, ChevronRight, Search } from "lucide-react";
import type { Game, IndexRecord } from "../../data/types";
import { loadData } from "../../data/client";
import { ResourceState } from "../../components/resource-state";
import { countLabel, title } from "../../lib/utils";
import { SectionIcon } from "../../components/section-icon";
import { matchSearch, type SearchEntry } from "./match";
import { recordContext, sharedLabels } from "../records/same-name";

export function GameSearch({ game }: { game: Game }) {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  return (
    <>
      <h1>Search {game.name.replace("Pokémon ", "")}</h1>
      <label className="search-field panel">
        <Search size={18} />
        <span className="sr-only">Search this game</span>
        <input
          autoFocus
          placeholder="Search records and guides…"
          value={query}
          onChange={(event) =>
            setParams(event.target.value ? { q: event.target.value } : {}, {
              replace: true,
            })
          }
        />
      </label>
      {query.trim() && (
        <SearchResults key={game.id} game={game} query={query} />
      )}
    </>
  );
}

function SearchResults({ game, query }: { game: Game; query: string }) {
  const [results, setResults] = useState<SearchEntry[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const search = async () => {
      const [indexes, guides] = await Promise.all([
        Promise.all(
          Object.entries(game.sections).map(async ([section, definition]) => {
            const index = await loadData<{ records: IndexRecord[] }>(
              definition.index,
            );
            const shared = sharedLabels(index.records);
            return index.records.map((record) => {
              const context = shared.has(record.label)
                ? recordContext(section, record)
                : undefined;
              return {
                label: record.label,
                section,
                path: `/${game.id}/${section}/${record.id}`,
                sprite: record.sprite,
                context,
              };
            });
          }),
        ),
        loadData<{ id: string; label: string; search: string }[]>(
          game.search_index,
        ),
      ]);
      if (active) {
        setResults([
          ...indexes.flat(),
          ...guides.map((guide) => ({
            label: guide.label,
            path: `/${game.id}/docs/${guide.id}`,
            section: "Documentation",
            search: guide.search,
          })),
        ]);
        setLoaded(true);
      }
    };
    search().catch((reason: unknown) => {
      if (active)
        setError(
          reason instanceof Error ? reason.message : "Search could not load.",
        );
    });
    return () => {
      active = false;
    };
  }, [game, attempt]);
  if (error)
    return (
      <ResourceState
        error={error}
        retry={() => {
          setError("");
          setAttempt((value) => value + 1);
        }}
      />
    );
  if (!loaded) return <p role="status">Loading this game's search index…</p>;
  const matches = matchSearch(results, query);
  return (
    <>
      <p className="results-line">{countLabel(matches.length, "result")}</p>
      <div className="search-results">
        {matches.slice(0, 100).map((result) => (
          <Link className="panel" key={result.path} to={result.path}>
            <span className="result-icon">
              {result.sprite ? (
                <img
                  src={result.sprite}
                  alt=""
                  width={32}
                  height={32}
                  loading="lazy"
                />
              ) : result.section === "Documentation" ? (
                <BookOpen size={18} aria-hidden="true" />
              ) : (
                <SectionIcon section={result.section} size={18} />
              )}
            </span>
            <span className="result-label">
              {result.label}
              {result.context && (
                <span className="result-context">{result.context}</span>
              )}
            </span>
            <small className="badge">{title(result.section)}</small>
            <ChevronRight size={15} />
          </Link>
        ))}
      </div>
      {matches.length > 100 && (
        <p>Narrow your search to see more specific results.</p>
      )}
      {!matches.length && <p>No records or guides match your search.</p>}
    </>
  );
}
