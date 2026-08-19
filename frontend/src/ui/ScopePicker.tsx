import { Search } from "lucide-react";
import { useId, useMemo, useState } from "react";

type ScopeOption = {
  id: string;
  label: string;
  detail?: string;
  /** Renders under its parent, the way the Brand tree reads elsewhere. */
  nested?: boolean;
};

type ScopePickerProps = {
  options: ScopeOption[];
  selectedId: string;
  onSelect: (id: string) => void;
  emptyLabel?: string;
};

export function ScopePicker({
  options,
  selectedId,
  onSelect,
  emptyLabel = "No matching results",
}: ScopePickerProps) {
  const [search, setSearch] = useState("");
  const searchId = useId();
  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return options;
    // A search result stands on its own: indenting a child whose parent was
    // filtered out would place it under whichever row happened to precede it.
    return options
      .filter((option) =>
        `${option.label} ${option.detail ?? ""}`.toLocaleLowerCase().includes(needle),
      )
      .map((option) => ({ ...option, nested: false }));
  }, [options, search]);

  return (
    <div className="scope-picker">
      {options.length > 5 && (
        <label className="scope-search" htmlFor={searchId}>
          <Search aria-hidden="true" size={16} />
          <input
            autoFocus
            id={searchId}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search"
            type="search"
            value={search}
          />
        </label>
      )}
      <div className="scope-options" role="listbox">
        {filtered.map((option) => (
          <button
            aria-selected={option.id === selectedId}
              className={option.nested ? "scope-option scope-option-nested" : "scope-option"}
            key={option.id}
            onClick={() => onSelect(option.id)}
            role="option"
            type="button"
          >
            <span>{option.label}</span>
            {option.detail && <small>{option.detail}</small>}
          </button>
        ))}
        {filtered.length === 0 && <p className="scope-empty">{emptyLabel}</p>}
      </div>
    </div>
  );
}
