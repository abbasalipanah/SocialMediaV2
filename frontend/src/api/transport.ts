import type { ZodType } from "zod";

import { apiProblemSchema } from "./contracts";

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? "";
export const API_BASE_URL = configuredBase.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function responseError(response: Response): Promise<ApiError> {
  let detail = `request_failed_${response.status}`;
  try {
    const body = apiProblemSchema.parse(await response.json());
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // The status is still authoritative when a proxy returns a non-JSON body.
  }
  return new ApiError(response.status, detail);
}

export async function apiQuery<T>(
  path: string,
  schema: ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw await responseError(response);
  return schema.parse(await response.json());
}

export async function apiCommand(path: string, init: RequestInit): Promise<void> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!response.ok) throw await responseError(response);
}

export async function apiMutation<T>(
  path: string,
  schema: ZodType<T>,
  init: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!response.ok) throw await responseError(response);
  return schema.parse(await response.json());
}

export function queryString(
  values: Record<string, boolean | number | string | undefined>,
): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value));
  });
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}
