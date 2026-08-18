const COUNTRY_CODE_ALIASES: Record<string, string> = {
  "cabo verde": "CV",
  "cape verde": "CV",
  "czech republic": "CZ",
  "democratic republic of the congo": "CD",
  "great britain": "GB",
  "hong kong sar china": "HK",
  "iran islamic republic of": "IR",
  "ivory coast": "CI",
  kosovo: "XK",
  laos: "LA",
  macedonia: "MK",
  moldova: "MD",
  palestine: "PS",
  "republic of korea": "KR",
  "russian federation": "RU",
  "south korea": "KR",
  syria: "SY",
  turkey: "TR",
  turkiye: "TR",
  "u k": "GB",
  "u s": "US",
  "u s a": "US",
  uk: "GB",
  "united states of america": "US",
  usa: "US",
  "viet nam": "VN",
};

const COUNTRY_CODE_NORMALIZATION: Record<string, string> = {
  EL: "GR",
  UK: "GB",
};

const regionNames = typeof Intl.DisplayNames === "function"
  ? new Intl.DisplayNames(["en"], { type: "region" })
  : null;

function normalizedLookup(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("en-US")
    .replace(/[^a-z0-9]+/gu, " ")
    .trim();
}

function displayNameForCode(code: string): string | null {
  try {
    const name = regionNames?.of(code);
    return name && name !== code ? name : null;
  } catch {
    return null;
  }
}

let nameToCode: Map<string, string> | null = null;

function countryNamesByCode(): Map<string, string> {
  if (nameToCode) return nameToCode;
  const values = new Map<string, string>();
  for (let first = 65; first <= 90; first += 1) {
    for (let second = 65; second <= 90; second += 1) {
      const code = String.fromCharCode(first, second);
      const name = displayNameForCode(code);
      if (name) values.set(normalizedLookup(name), code);
    }
  }
  for (const [name, code] of Object.entries(COUNTRY_CODE_ALIASES)) {
    values.set(normalizedLookup(name), code);
  }
  nameToCode = values;
  return values;
}

export function countryCode(value: string): string | null {
  const raw = value.trim();
  if (/^[a-z]{2}$/iu.test(raw)) {
    const upper = raw.toUpperCase();
    const normalized = COUNTRY_CODE_NORMALIZATION[upper] ?? upper;
    return displayNameForCode(normalized) ? normalized : null;
  }
  return countryNamesByCode().get(normalizedLookup(raw)) ?? null;
}

export function countryDisplayName(value: string): string {
  const code = countryCode(value);
  if (code) return displayNameForCode(code) ?? value.trim();
  return value
    .trim()
    .replaceAll("_", " ")
    .replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase("en-US"));
}

export function countryLookupKey(value: string): string {
  const code = countryCode(value);
  const name = code ? displayNameForCode(code) ?? value : value;
  const normalized = normalizedLookup(name);
  if (code === "TR") return "turkey";
  if (code === "US") return "united states of america";
  return normalized;
}

export function countryFlagSrc(value: string): string | null {
  const code = countryCode(value);
  return code ? `/flags/${code.toLowerCase()}.svg` : null;
}

export function CountryTableLabel({ value }: { value: string }) {
  const name = countryDisplayName(value);
  const flag = countryFlagSrc(value);
  return (
    <span className="country-table-label">
      {/* An image rather than the regional-indicator emoji: Windows renders no
          flag for those code points and shows the two letters instead, so the
          country appeared as a bare abbreviation next to an empty circle. */}
      {flag ? <img alt="" className="country-flag" src={flag} /> : null}
      <span>{name}</span>
    </span>
  );
}
