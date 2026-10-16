import {
  Backpack,
  Database,
  Footprints,
  MapPin,
  PawPrint,
  Shapes,
  Sparkles,
  Swords,
  Users,
  type LucideProps,
} from "lucide-react";

const ICONS = {
  abilities: Sparkles,
  encounters: Footprints,
  items: Backpack,
  locations: MapPin,
  moves: Swords,
  pokemon: PawPrint,
  trainers: Users,
  types: Shapes,
};

export function SectionIcon({
  section,
  ...props
}: { section: string } & LucideProps) {
  const Icon = ICONS[section as keyof typeof ICONS] ?? Database;
  return <Icon aria-hidden="true" {...props} />;
}
