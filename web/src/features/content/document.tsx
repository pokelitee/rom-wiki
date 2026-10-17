import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { isValidElement, type ReactNode } from "react";
import type { Game } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";
import { headingSlug, outline, type OutlineEntry } from "./outline";

function headingId(children: ReactNode): string {
  const text = (node: ReactNode): string =>
    Array.isArray(node)
      ? node.map(text).join("")
      : isValidElement<{ children?: ReactNode }>(node)
        ? text(node.props.children)
        : String(node ?? "");
  return headingSlug(text(children));
}

function Contents({ entries }: { entries: OutlineEntry[] }) {
  return (
    <nav className="guide-contents" aria-label="On this page">
      <p className="nav-label">On this page</p>
      <ol>
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#${entry.id}`}
              onClick={(event) => {
                event.preventDefault();
                document.getElementById(entry.id)?.scrollIntoView();
              }}
            >
              {entry.text}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

// Guides are titled by the page header, so a leading "# Title" in the
// Markdown would repeat it.
function withoutTitle(markdown: string): string {
  return markdown.replace(/^\s*# [^\n]*\n?/, "");
}

export function Document({
  game,
  id,
  titled = true,
}: {
  game: Game;
  id: string;
  titled?: boolean;
}) {
  const entry = game.documents.find((document) => document.id === id);
  const resource = useResource<{ markdown: string }>(entry?.path);
  if (!entry)
    return (
      <div className="notice">
        <h1>Guide not found</h1>
        <Link to={`/${game.id}`}>Back to game</Link>
      </div>
    );
  return (
    <ResourceState error={resource.error} retry={resource.retry}>
      {resource.value && titled && (
        <header className="page-heading">
          <div>
            <p className="eyebrow">Documentation</p>
            <h1>{entry.label}</h1>
          </div>
        </header>
      )}
      {resource.value && (
        <div className="guide-layout">
          <article className="prose panel">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 id={headingId(children)}>{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 id={headingId(children)}>{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 id={headingId(children)}>{children}</h3>
                ),
                h4: ({ children }) => (
                  <h4 id={headingId(children)}>{children}</h4>
                ),
                a: ({ href, children }) => {
                  if (href?.startsWith("#"))
                    return (
                      <a
                        href={href}
                        onClick={(event) => {
                          event.preventDefault();
                          document
                            .getElementById(decodeURIComponent(href.slice(1)))
                            ?.scrollIntoView();
                        }}
                      >
                        {children}
                      </a>
                    );
                  if (href && !/^(https?:|mailto:|#)/.test(href)) {
                    const resolved = new URL(
                      href,
                      `https://romwiki.local/${id}.md`,
                    );
                    const doc = resolved.pathname.slice(1).replace(/\.md$/, "");
                    const [section, record] = doc.split("/");
                    if (section === "data")
                      return (
                        <Link to={`/${game.id}/downloads`}>{children}</Link>
                      );
                    if (section === "changes")
                      return <Link to={`/${game.id}/changes`}>{children}</Link>;
                    if (section in game.sections)
                      return (
                        <Link
                          to={`/${game.id}/${section}${record && record !== "index" ? `/${record}` : ""}`}
                        >
                          {children}
                        </Link>
                      );
                    return (
                      <Link to={`/${game.id}/docs/${doc}`}>{children}</Link>
                    );
                  }
                  return <a href={href}>{children}</a>;
                },
              }}
            >
              {titled
                ? withoutTitle(resource.value.markdown)
                : resource.value.markdown}
            </ReactMarkdown>
          </article>
          {outline(resource.value.markdown).length >= 3 && (
            <Contents entries={outline(resource.value.markdown)} />
          )}
        </div>
      )}
    </ResourceState>
  );
}
