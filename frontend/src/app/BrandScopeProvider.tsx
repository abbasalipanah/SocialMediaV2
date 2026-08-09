import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  apiQuery,
  brandWorkspaceSchema,
  queryString,
  workspaceCapabilitiesSchema,
  type Platform,
  type WorkspaceBrand,
  type WorkspaceCapabilities,
} from "../api";
import { useAuth } from "../auth";

const PLATFORMS: Platform[] = ["facebook", "instagram", "tiktok"];

type AccountSelections = Partial<Record<Platform, number | "all">>;

export type BrandScopeContextValue = {
  workspace: ReturnType<typeof brandWorkspaceSchema.parse> | null;
  capabilities: WorkspaceCapabilities | null;
  isLoading: boolean;
  error: Error | null;
  parentBrands: WorkspaceBrand[];
  childBrands: WorkspaceBrand[];
  parentBrand: WorkspaceBrand | null;
  selectedBrand: WorkspaceBrand | null;
  selectedBrandId: string;
  rollup: boolean;
  selectParent: (brandId: string) => void;
  selectChild: (brandId: string | "all") => void;
  accountSelections: AccountSelections;
  selectAccount: (platform: Platform, accountId: number | "all") => void;
};

const BrandScopeContext = createContext<BrandScopeContextValue | null>(null);

function selectedBrandStorageKey(userId: string): string {
  return `social-media-v2:selected-brand:${userId}`;
}

function selectedAccountStorageKey(userId: string, platform: Platform): string {
  return `social-media-v2:selected-account:${userId}:${platform}`;
}

export function BrandScopeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user) throw new Error("BrandScopeProvider requires an authenticated user");

  const [selectedBrandId, setSelectedBrandId] = useState(user.brand_id);
  const [accountSelections, setAccountSelections] = useState<AccountSelections>({});
  const hydratedFor = useRef<string | null>(null);

  const workspaceQuery = useQuery({
    queryKey: ["workspace", "brands", user.user_id, user.brand_id],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/workspace/brands${queryString({ selected_brand_id: user.brand_id })}`,
        brandWorkspaceSchema,
        signal,
      ),
  });

  const workspace = workspaceQuery.data ?? null;
  const brandIds = useMemo(
    () => new Set(workspace?.brands.map((brand) => brand.brand_id) ?? []),
    [workspace],
  );
  const workspaceScopeKey = useMemo(
    () => [...brandIds].sort().join(","),
    [brandIds],
  );

  useEffect(() => {
    if (!workspace) return;
    const hydrationKey = `${user.user_id}:${user.brand_id}:${workspaceScopeKey}`;
    if (hydratedFor.current === hydrationKey) return;
    hydratedFor.current = hydrationKey;
    const stored = window.localStorage.getItem(selectedBrandStorageKey(user.user_id));
    const defaultBrandId = brandIds.has(user.brand_id)
      ? user.brand_id
      : workspace.default_brand_id;
    const storedBrandIsValid = Boolean(stored && brandIds.has(stored));
    setSelectedBrandId(storedBrandIsValid && stored ? stored : defaultBrandId);
    if (stored && !storedBrandIsValid) {
      window.localStorage.setItem(selectedBrandStorageKey(user.user_id), defaultBrandId);
      PLATFORMS.forEach((platform) =>
        window.localStorage.removeItem(selectedAccountStorageKey(user.user_id, platform)),
      );
      setAccountSelections({});
      return;
    }
    const remembered: AccountSelections = {};
    PLATFORMS.forEach((platform) => {
      const value = window.localStorage.getItem(selectedAccountStorageKey(user.user_id, platform));
      if (value === "all") remembered[platform] = "all";
      else if (value && Number.isSafeInteger(Number(value))) remembered[platform] = Number(value);
    });
    setAccountSelections(remembered);
  }, [brandIds, user.brand_id, user.user_id, workspace, workspaceScopeKey]);

  const selectedFamily = useMemo(
    () => workspace?.families.find((family) => family.brand_ids.includes(selectedBrandId)) ?? null,
    [selectedBrandId, workspace],
  );
  const parentBrand =
    workspace?.brands.find((brand) => brand.brand_id === selectedFamily?.root_brand_id) ?? null;
  const selectedBrand =
    workspace?.brands.find((brand) => brand.brand_id === selectedBrandId) ?? null;
  const childBrands = useMemo(
    () =>
      (workspace?.brands ?? []).filter(
        (brand) =>
          selectedFamily?.brand_ids.includes(brand.brand_id) &&
          brand.brand_id !== selectedFamily.root_brand_id &&
          brand.visibility === "active",
      ),
    [selectedFamily, workspace],
  );
  const parentBrands = useMemo(
    () =>
      (workspace?.families ?? [])
        .map((family) => workspace?.brands.find((brand) => brand.brand_id === family.root_brand_id))
        .filter((brand): brand is WorkspaceBrand => Boolean(brand)),
    [workspace],
  );
  const rollup = Boolean(
    selectedFamily && selectedBrandId === selectedFamily.root_brand_id && childBrands.length > 0,
  );

  const capabilitiesQuery = useQuery({
    enabled: Boolean(workspace && brandIds.has(selectedBrandId)),
    queryKey: ["workspace", "capabilities", selectedBrandId, rollup],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/workspace/capabilities${queryString({
          selected_brand_id: selectedBrandId,
          rollup,
        })}`,
        workspaceCapabilitiesSchema,
        signal,
      ),
  });

  const resetAccounts = useCallback(() => {
    setAccountSelections({});
    PLATFORMS.forEach((platform) =>
      window.localStorage.removeItem(selectedAccountStorageKey(user.user_id, platform)),
    );
  }, [user.user_id]);

  const persistBrand = useCallback(
    (brandId: string) => {
      setSelectedBrandId(brandId);
      window.localStorage.setItem(selectedBrandStorageKey(user.user_id), brandId);
      resetAccounts();
    },
    [resetAccounts, user.user_id],
  );

  const selectParent = useCallback(
    (brandId: string) => {
      const currentWorkspace = workspace;
      const family = currentWorkspace?.families.find((item) => item.root_brand_id === brandId);
      if (!family || !currentWorkspace) return;
      const activeChildren = family.brand_ids.filter(
        (id) =>
          id !== brandId && currentWorkspace.brands.some((brand) => brand.brand_id === id),
      );
      persistBrand(activeChildren.length > 0 ? brandId : family.brand_ids[0] ?? brandId);
    },
    [persistBrand, workspace],
  );

  const selectChild = useCallback(
    (brandId: string | "all") => {
      if (!selectedFamily) return;
      persistBrand(brandId === "all" ? selectedFamily.root_brand_id : brandId);
    },
    [persistBrand, selectedFamily],
  );

  const selectAccount = useCallback(
    (platform: Platform, accountId: number | "all") => {
      setAccountSelections((current) => ({ ...current, [platform]: accountId }));
      window.localStorage.setItem(
        selectedAccountStorageKey(user.user_id, platform),
        String(accountId),
      );
    },
    [user.user_id],
  );

  const value: BrandScopeContextValue = {
    workspace,
    capabilities: capabilitiesQuery.data ?? null,
    isLoading: workspaceQuery.isPending || capabilitiesQuery.isPending,
    error: workspaceQuery.error ?? capabilitiesQuery.error,
    parentBrands,
    childBrands,
    parentBrand,
    selectedBrand,
    selectedBrandId,
    rollup,
    selectParent,
    selectChild,
    accountSelections,
    selectAccount,
  };

  return <BrandScopeContext.Provider value={value}>{children}</BrandScopeContext.Provider>;
}

export function useBrandScope(): BrandScopeContextValue {
  const value = useContext(BrandScopeContext);
  if (!value) throw new Error("useBrandScope must be used inside BrandScopeProvider");
  return value;
}
