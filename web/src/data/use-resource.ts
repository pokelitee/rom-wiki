import { useEffect, useState } from "react";
import { loadData } from "./client";

export function useResource<T>(path: string | undefined) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    path?: string;
    value?: T;
    error?: string;
  }>({});
  useEffect(() => {
    let active = true;
    if (path) {
      loadData<T>(path).then(
        (value) => {
          if (active) setState({ path, value });
        },
        (error: unknown) => {
          if (active)
            setState({
              path,
              error:
                error instanceof Error ? error.message : "Could not load data.",
            });
        },
      );
    }
    return () => {
      active = false;
    };
  }, [path, attempt]);
  return {
    value: state.path === path ? state.value : undefined,
    error: state.path === path ? state.error : undefined,
    retry: () => {
      setState({});
      setAttempt((value) => value + 1);
    },
  };
}
