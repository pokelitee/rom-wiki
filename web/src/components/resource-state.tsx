import type { ReactNode } from "react";
import { Button } from "./ui/button";

export function ResourceState({
  error,
  retry,
  children,
}: {
  error?: string;
  retry: () => void;
  children?: ReactNode;
}) {
  if (error)
    return (
      <div className="notice" role="alert">
        <p>{error}</p>
        <Button onClick={retry} variant="outline">
          Retry
        </Button>
      </div>
    );
  if (!children)
    return (
      <div role="status" className="loading">
        <span className="loading-dot" /> Loading game data…
      </div>
    );
  return children;
}
