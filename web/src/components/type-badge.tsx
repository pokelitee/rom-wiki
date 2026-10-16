import { title } from "../lib/utils";

export function TypeBadge({ name }: { name: string }) {
  return (
    <span className="badge type-badge" data-type={name.toLowerCase()}>
      {title(name)}
    </span>
  );
}
