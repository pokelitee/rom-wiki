import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { isValidElement, type ReactNode } from "react";
import type { Game } from "../../data/types";
import { useResource } from "../../data/use-resource";
import { ResourceState } from "../../components/resource-state";

function headingId(children: ReactNode): string {
  const text = (node: ReactNode): string =>
    Array.isArray(node)
      ? node.map(text).join("")
      : isValidElement<{ children?: ReactNode }>(node)
        ? text(node.props.children)
        : String(node ?? "");
  return text(children)
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s/g, "-");
}

export function Document({ game, id }: { game: Game; id: string }) {
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
      {resource.value && (
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
                    return <Link to={`/${game.id}/downloads`}>{children}</Link>;
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
                  return <Link to={`/${game.id}/docs/${doc}`}>{children}</Link>;
                }
                return <a href={href}>{children}</a>;
              },
            }}
          >
            {resource.value.markdown}
          </ReactMarkdown>
        </article>
      )}
    </ResourceState>
  );
}
