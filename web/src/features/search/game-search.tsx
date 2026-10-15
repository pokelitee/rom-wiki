import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronRight, Search } from "lucide-react";
import type { Game } from "../../data/types";
import { loadData } from "../../data/client";
import { title } from "../../lib/utils";

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
  const [results, setResults] = useState<
    { label: string; path: string; section: string; search?: string }[]
  >([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    const search = async () => {
      const indexes = await Promise.all(
        Object.entries(game.sections).map(async ([section, definition]) => {
          const index = await loadData<{
            records: { id: string; label: string }[];
          }>(definition.index);
          return index.records.map((record) => ({
            label: record.label,
            section,
            path: `/${game.id}/${section}/${record.id}`,
          }));
        }),
      );
      const guides = await loadData<
        { id: string; label: string; search: string }[]
      >(game.search_index);
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
  }, [game]);
  if (error) return <p role="alert">{error}</p>;
  if (!loaded) return <p role="status">Loading this game's search index…</p>;
  const term = query.trim().toLocaleLowerCase();
  const matches = results.filter((result) =>
    (result.search ?? result.label.toLocaleLowerCase()).includes(term),
  );
  return (
    <>
      <p className="results-line">{matches.length} results</p>
      <div className="search-results">
        {matches.slice(0, 100).map((result) => (
          <Link className="panel" key={result.path} to={result.path}>
            <span>{result.label}</span>
            <small>{title(result.section)}</small>
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
