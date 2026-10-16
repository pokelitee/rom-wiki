import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "./ui/button";

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
    } catch (error) {
      console.warn("Clipboard copy failed", error);
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2000);
  };
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={copy}
      aria-label={label}
      title={label}
    >
      {state === "copied" ? <Check size={14} /> : <Copy size={14} />}
      {state === "copied"
        ? "Copied"
        : state === "failed"
          ? "Copy failed"
          : "Copy"}
    </Button>
  );
}
