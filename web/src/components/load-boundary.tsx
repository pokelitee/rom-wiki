import { Component, type ReactNode } from "react";
import { Button } from "./ui/button";

// Pages load their code on demand. A tab left open across a deploy asks for
// files the new deploy replaced, so offer a reload instead of a blank page.
export class LoadBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("A page could not load", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="notice" role="alert">
        <p>This page could not load. The site may have just been updated.</p>
        <Button variant="outline" onClick={() => location.reload()}>
          Reload
        </Button>
      </div>
    );
  }
}
