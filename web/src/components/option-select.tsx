import { useId, type ReactNode } from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

export interface Option {
  value: string;
  label: ReactNode;
  group?: string;
}

// Radix reserves the empty string for "no selection", while the app uses it
// for "all"; this stands in for it inside the menu.
const ALL = "__all__";

export function OptionSelect({
  label,
  value,
  onChange,
  options,
  hideLabel = false,
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  hideLabel?: boolean;
  className?: string;
}) {
  const id = useId();
  const groups = [...new Set(options.map((option) => option.group ?? ""))];
  return (
    <div className={className ?? "option-select"}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : undefined}>
        {label}
      </label>
      <Select
        value={value || ALL}
        onValueChange={(next) => onChange(next === ALL ? "" : next)}
      >
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {groups.map((group) => (
            <SelectGroup key={group}>
              {group && <SelectLabel>{group}</SelectLabel>}
              {options
                .filter((option) => (option.group ?? "") === group)
                .map((option) => (
                  <SelectItem
                    key={option.value || ALL}
                    value={option.value || ALL}
                  >
                    {option.label}
                  </SelectItem>
                ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
