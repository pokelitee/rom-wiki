import { GameSearch } from "./features/search/game-search";
import { Downloads } from "./features/content/downloads";
import { GameHome } from "./features/content/game-home";
import { Portal } from "./features/portal/portal";
import { useEffect, useState } from "react";
import {
  HashRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Database,
  Download,
  GitCompareArrows,
  Library,
  Menu,
  Moon,
  Search,
  Sun,
  X,
} from "lucide-react";
import type { Game, Manifest } from "./data/types";
import { loadManifest } from "./data/client";
import { Button } from "./components/ui/button";
import { OptionSelect } from "./components/option-select";
import { SpriteProvider } from "./components/sprite-provider";
import { SectionIcon } from "./components/section-icon";
import { Catalog } from "./features/catalog/catalog";
import { Detail } from "./features/records/detail";
import { Document } from "./features/content/document";
import { Changes } from "./features/content/changes";
import { title } from "./lib/utils";

export function App() {
  const [manifest, setManifest] = useState<Manifest>();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    loadManifest().then(
      (value) => {
        if (active) setManifest(value);
      },
      (reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load the game library.",
          );
      },
    );
    return () => {
      active = false;
    };
  }, [attempt]);
  return (
    <HashRouter>
      {manifest ? (
        <Shell manifest={manifest} />
      ) : (
        <main className="startup">
          <h1>ROM Wiki</h1>
          {error ? (
            <>
              <p role="alert">{error}</p>
              <Button
                onClick={() => {
                  setError("");
                  setAttempt((value) => value + 1);
                }}
              >
                Retry
              </Button>
            </>
          ) : (
            <p role="status">Loading the game library…</p>
          )}
        </main>
      )}
    </HashRouter>
  );
}

function Shell({ manifest }: { manifest: Manifest }) {
  const location = useLocation();
  const navigate = useNavigate();
  const game = manifest.games.find(
    (entry) => location.pathname.split("/")[1] === entry.id,
  );
  const [menu, setMenu] = useState(false);
  const [dark, setDark] = useState(() => {
    try {
      return (
        localStorage.getItem("romwiki.color-scheme") === "slate" ||
        (!localStorage.getItem("romwiki.color-scheme") &&
          matchMedia("(prefers-color-scheme: dark)").matches)
      );
    } catch {
      return matchMedia("(prefers-color-scheme: dark)").matches;
    }
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("romwiki.color-scheme", dark ? "slate" : "default");
    } catch (error) {
      console.warn("Theme preference could not be saved", error);
    }
  }, [dark]);
  useEffect(() => {
    document.documentElement.dataset.theme = game?.theme ?? "portal";
    document.title = game ? `${game.name} · ROM Wiki` : "ROM Wiki";
    window.scrollTo(0, 0);
  }, [game, location.pathname]);
  return (
    <>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link className="brand" to="/">
            <span className="brand-mark">
              <Database size={19} />
            </span>
            ROM<span>Wiki</span>
          </Link>
          <span className="header-divider" />
          <OptionSelect
            className="game-picker"
            label="Choose a game"
            hideLabel
            value={game?.id ?? ""}
            onChange={(value) => {
              navigate(value ? `/${value}` : "/");
              setMenu(false);
            }}
            options={[
              { value: "", label: "Game library" },
              ...manifest.games.map((entry) => ({
                value: entry.id,
                group: `Generation ${entry.generation}`,
                label: (
                  <span className="game-option">
                    <span className="theme-dot" data-theme={entry.theme} />
                    {entry.name.replace("Pokémon ", "")}
                  </span>
                ),
              })),
            ]}
          />
          <div className="header-actions">
            <a
              className="source-link"
              href="https://github.com/pokelitee/rom-wiki"
              target="_blank"
              rel="noreferrer"
            >
              Source
              <ArrowUpRight size={14} />
            </a>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDark((value) => !value)}
              aria-label={dark ? "Use light theme" : "Use dark theme"}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
            {game && (
              <Button
                variant="ghost"
                size="icon"
                className="menu-toggle"
                aria-label={menu ? "Close navigation" : "Open navigation"}
                aria-expanded={menu}
                aria-controls="game-navigation"
                onClick={() => setMenu((value) => !value)}
              >
                {menu ? <X size={19} /> : <Menu size={19} />}
              </Button>
            )}
          </div>
        </div>
      </header>
      <div className={game ? "app-layout" : "portal-layout"}>
        {game && (
          <aside
            id="game-navigation"
            className={`sidebar ${menu ? "is-open" : ""}`}
          >
            <div className="sidebar-game">
              <p className="eyebrow">Generation {game.generation}</p>
              <strong>{game.name.replace("Pokémon ", "")}</strong>
            </div>
            <nav aria-label="Game navigation" onClick={() => setMenu(false)}>
              <NavLink end to={`/${game.id}`}>
                <BookOpen size={16} />
                Overview
              </NavLink>
              <NavLink to={`/${game.id}/search`}>
                <Search size={16} />
                Search this game
              </NavLink>
              <p className="nav-label">Game data</p>
              {Object.keys(game.sections).map((section) => (
                <NavLink key={section} to={`/${game.id}/${section}`}>
                  <SectionIcon section={section} size={16} />
                  {title(section)}
                  <ChevronRight className="nav-chevron" size={13} />
                </NavLink>
              ))}
              {Object.keys(game.comparisons).length > 0 && (
                <NavLink to={`/${game.id}/changes`}>
                  <GitCompareArrows size={16} />
                  Changes
                </NavLink>
              )}
              <NavLink to={`/${game.id}/downloads`}>
                <Download size={16} />
                Data downloads
              </NavLink>
              <p className="nav-label">Documentation</p>
              {game.documents
                .filter((entry) => entry.id !== "index")
                .map((entry) => (
                  <NavLink key={entry.id} to={`/${game.id}/docs/${entry.id}`}>
                    {entry.label}
                  </NavLink>
                ))}
              <div className="sidebar-bottom">
                <Link to="/">
                  <Library size={15} />
                  All games
                </Link>
                <p>
                  ROM-derived mechanics.
                  <br />
                  Sources and limitations documented.
                </p>
              </div>
            </nav>
          </aside>
        )}
        <main id="main-content" tabIndex={-1} className="main-content">
          <Routes>
            <Route path="/" element={<Portal games={manifest.games} />} />
            <Route
              path="/:gameId/*"
              element={<GameRoutes games={manifest.games} />}
            />
            <Route path="*" element={<NotFound />} />
          </Routes>
          <footer>
            ROM Wiki <span>·</span> An independent, data-driven reference.
            Pokémon belongs to its respective owners.
          </footer>
        </main>
      </div>
    </>
  );
}

function GameRoutes({ games }: { games: Game[] }) {
  const { gameId } = useParams();
  const game = games.find((entry) => entry.id === gameId);
  if (!game) return <NotFound />;
  return (
    <SpriteProvider game={game}>
      <Routes>
        <Route index element={<GameHome game={game} />} />
        <Route path="search" element={<GameSearch game={game} />} />
        <Route path="downloads" element={<Downloads game={game} />} />
        <Route
          path="changes"
          element={
            Object.keys(game.comparisons).length ? (
              <Changes game={game} />
            ) : (
              <NotFound />
            )
          }
        />
        <Route path="docs/*" element={<DocumentRoute game={game} />} />
        <Route path=":section" element={<SectionRoute game={game} />} />
        <Route
          path=":section/:recordId"
          element={<SectionRoute game={game} />}
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </SpriteProvider>
  );
}

function SectionRoute({ game }: { game: Game }) {
  const { section = "", recordId } = useParams();
  if (!(section in game.sections)) return <NotFound />;
  return recordId ? (
    <Detail game={game} section={section} id={recordId} />
  ) : (
    <Catalog key={`${game.id}/${section}`} game={game} section={section} />
  );
}

function DocumentRoute({ game }: { game: Game }) {
  const params = useParams();
  return <Document game={game} id={params["*"] ?? "index"} />;
}

function NotFound() {
  return (
    <div className="empty-state">
      <h1>Page not found</h1>
      <p>This game or section is not available.</p>
      <Link to="/">Back to the game library</Link>
    </div>
  );
}
