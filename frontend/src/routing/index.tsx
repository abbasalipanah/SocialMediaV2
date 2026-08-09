import {
  Children,
  createContext,
  isValidElement,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type Location = {
  pathname: string;
  search: string;
  hash: string;
  state: unknown;
};

type To = string | {
  pathname?: string;
  search?: string;
  hash?: string;
};

type NavigateOptions = {
  replace?: boolean;
  state?: unknown;
};

type NavigateFunction = (to: To, options?: NavigateOptions) => void;

type RouterValue = {
  location: Location;
  navigate: NavigateFunction;
};

const RouterContext = createContext<RouterValue | null>(null);
const OutletContext = createContext<ReactNode>(null);

function browserLocation(): Location {
  return {
    pathname: window.location.pathname || "/",
    search: window.location.search,
    hash: window.location.hash,
    state: window.history.state,
  };
}

function locationFrom(to: To, current: Location, state: unknown): Location {
  if (typeof to === "string") {
    const parsed = new URL(to, `http://social-media-v2${current.pathname}${current.search}`);
    return {
      pathname: parsed.pathname || "/",
      search: parsed.search,
      hash: parsed.hash,
      state,
    };
  }
  const pathname = to.pathname ?? current.pathname;
  const rawSearch = to.search ?? "";
  const rawHash = to.hash ?? "";
  return {
    pathname: pathname.startsWith("/") ? pathname : `/${pathname}`,
    search: rawSearch && !rawSearch.startsWith("?") ? `?${rawSearch}` : rawSearch,
    hash: rawHash && !rawHash.startsWith("#") ? `#${rawHash}` : rawHash,
    state,
  };
}

function hrefFor(location: Location): string {
  return `${location.pathname}${location.search}${location.hash}`;
}

export function BrowserRouter({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<Location>(browserLocation);
  const locationRef = useRef(location);
  locationRef.current = location;

  useEffect(() => {
    const onPopState = () => {
      const next = browserLocation();
      locationRef.current = next;
      setLocation(next);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback<NavigateFunction>((to, options = {}) => {
    const next = locationFrom(to, locationRef.current, options.state ?? null);
    if (options.replace) window.history.replaceState(next.state, "", hrefFor(next));
    else window.history.pushState(next.state, "", hrefFor(next));
    locationRef.current = next;
    setLocation(next);
  }, []);

  const value = useMemo(() => ({ location, navigate }), [location, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function MemoryRouter({
  children,
  initialEntries = ["/"],
}: {
  children: ReactNode;
  initialEntries?: string[];
}) {
  const initialEntry = initialEntries.at(-1) ?? "/";
  const [location, setLocation] = useState<Location>(() => locationFrom(
    initialEntry,
    { pathname: "/", search: "", hash: "", state: null },
    null,
  ));
  const navigate = useCallback<NavigateFunction>((to, options = {}) => {
    setLocation((current) => locationFrom(to, current, options.state ?? null));
  }, []);
  const value = useMemo(() => ({ location, navigate }), [location, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

function useRouter(): RouterValue {
  const router = useContext(RouterContext);
  if (!router) throw new Error("Routing components must be rendered inside a router");
  return router;
}

export function useLocation(): Location {
  return useRouter().location;
}

export function useNavigate(): NavigateFunction {
  return useRouter().navigate;
}

export function useSearchParams(): [URLSearchParams] {
  const { search } = useLocation();
  return useMemo(() => [new URLSearchParams(search)], [search]);
}

export function Navigate({
  replace = false,
  state,
  to,
}: NavigateOptions & { to: To }) {
  const navigate = useNavigate();
  useEffect(() => navigate(to, { replace, state }), [navigate, replace, state, to]);
  return null;
}

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: To };

export function Link({ children, onClick, target, to, ...props }: LinkProps) {
  const { location, navigate } = useRouter();
  const destination = locationFrom(to, location, null);
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey ||
      (target && target !== "_self")
    ) return;
    event.preventDefault();
    navigate(to);
  };
  return (
    <a {...props} href={hrefFor(destination)} onClick={handleClick} target={target}>
      {children}
    </a>
  );
}

type NavLinkProps = Omit<LinkProps, "className"> & {
  className?: string | ((state: { isActive: boolean }) => string);
};

export function NavLink({ className, to, ...props }: NavLinkProps) {
  const location = useLocation();
  const destination = locationFrom(to, location, null);
  const path = destination.pathname.replace(/\/$/, "") || "/";
  const current = location.pathname.replace(/\/$/, "") || "/";
  const isActive = current === path || (path !== "/" && current.startsWith(`${path}/`));
  const resolvedClassName = typeof className === "function" ? className({ isActive }) : className;
  return (
    <Link
      {...props}
      aria-current={isActive ? "page" : undefined}
      className={resolvedClassName}
      to={to}
    />
  );
}

type RouteProps = {
  children?: ReactNode;
  element?: ReactNode;
  index?: boolean;
  path?: string;
};

export function Route(_: RouteProps) {
  return null;
}

function pathSegments(pathname: string): string[] {
  return pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
}

function withOutlet(element: ReactNode, outlet: ReactNode): ReactElement {
  return (
    <OutletContext.Provider value={outlet}>
      {element}
    </OutletContext.Provider>
  );
}

function renderMatch(children: ReactNode, segments: string[], offset = 0): ReactNode | null {
  for (const child of Children.toArray(children)) {
    if (!isValidElement<RouteProps>(child) || child.type !== Route) continue;
    const { children: nestedRoutes, element = null, index = false, path } = child.props;

    if (index) {
      if (offset === segments.length) return withOutlet(element, null);
      continue;
    }

    if (path === undefined) {
      const nested = renderMatch(nestedRoutes, segments, offset);
      if (nested !== null) return withOutlet(element, nested);
      if (!nestedRoutes && offset === segments.length) return withOutlet(element, null);
      continue;
    }

    if (path === "*") return withOutlet(element, null);
    const expected = pathSegments(path);
    const start = path.startsWith("/") ? 0 : offset;
    const matches = expected.every((part, index_) => segments[start + index_] === part);
    if (!matches) continue;
    const nextOffset = start + expected.length;
    const nested = renderMatch(nestedRoutes, segments, nextOffset);
    if (nested !== null) return withOutlet(element, nested);
    if (nextOffset === segments.length) return withOutlet(element, null);
  }
  return null;
}

export function Routes({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return renderMatch(children, pathSegments(pathname));
}

export function Outlet() {
  return useContext(OutletContext);
}
