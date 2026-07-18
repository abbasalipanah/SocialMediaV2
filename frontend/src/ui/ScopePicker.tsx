import { Search } from "lucide-react";
import { useId, useMemo, useState } from "react";

type ScopeOption = {
  id: string;
  label: string;
  detail?: string;
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
    return needle
      ? options.filter((option) =>
          `${option.label} ${option.detail ?? ""}`.toLocaleLowerCase().includes(needle),
        )
      : options;
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
            className="scope-option"
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
