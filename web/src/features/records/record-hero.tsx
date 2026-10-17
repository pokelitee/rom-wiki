import { useState } from "react";
import { Volume2 } from "lucide-react";
import type { DataObject, Json } from "../../data/types";
import { TypeBadge } from "../../components/type-badge";
import { Button } from "../../components/ui/button";
import { object } from "../../lib/json";

function SpriteViewer({
  sprites,
  fallback,
}: {
  sprites: DataObject[];
  fallback?: string;
}) {
  const [selected, setSelected] = useState(0);
  const current = sprites[selected] ?? sprites[0];
  const url = current ? String(current.url) : fallback;
  if (!url) return null;
  return (
    <div className="sprite-viewer">
      <img
        className="record-sprite"
        src={url}
        alt={String(current?.label ?? "")}
        width={112}
        height={112}
      />
      {sprites.length > 1 && (
        <div className="sprite-thumbs" role="group" aria-label="Sprites">
          {sprites.map((sprite, index) => (
            <button
              key={index}
              type="button"
              aria-label={String(sprite.label ?? `Sprite ${index + 1}`)}
              aria-pressed={index === selected}
              title={String(sprite.label ?? "")}
              onClick={() => setSelected(index)}
            >
              <img src={String(sprite.url)} alt="" width={32} height={32} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CryButton({ url }: { url: string }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        new Audio(url).play().catch((error: unknown) => {
          console.warn("The cry could not play", error);
        });
      }}
    >
      <Volume2 size={14} aria-hidden="true" />
      Play cry
    </Button>
  );
}

// The record's name, image, types, and the description its reference data
// provides, all in one card at the top of the page.
export function RecordHero({
  eyebrow,
  label,
  record,
  reference,
  types,
}: {
  eyebrow: string;
  label: string;
  record: DataObject;
  reference: DataObject;
  types: string[];
}) {
  const sprites = (Array.isArray(record.sprites) ? record.sprites : [])
    .map(object)
    .filter((sprite) => typeof sprite.url === "string");
  const fallback = object(record.sprite).url ?? reference.sprite_url;
  const description = reference.flavor_text ?? reference.short_effect;
  const cry = object(record.cry).url;
  const source = (value: Json | undefined) =>
    typeof value === "string" ? value : "";
  return (
    <div className="record-hero panel">
      <SpriteViewer
        sprites={sprites}
        fallback={typeof fallback === "string" ? fallback : undefined}
      />
      <div className="hero-body">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{label}</h1>
        {types.length > 0 && (
          <div className="badge-list">
            {types.map((name) => (
              <TypeBadge key={name} name={name} />
            ))}
          </div>
        )}
        {(description || reference.effect) && (
          <div className="hero-description">
            {description && <p>{String(description)}</p>}
            {reference.effect && reference.effect !== description && (
              <p className="muted">{String(reference.effect)}</p>
            )}
            <small>
              {source(reference.source)}
              {reference.flavor_text_source === "rom"
                ? " · Description decoded from ROM"
                : ""}
            </small>
          </div>
        )}
        {typeof cry === "string" && <CryButton url={cry} />}
      </div>
    </div>
  );
}
