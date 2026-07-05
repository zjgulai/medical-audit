export const staticBackendRuntime = {
  dynamicApiAvailable: false,
  reason: "MEDICAL_AUDIT_NEXT_EXPORT disables backend rewrites; use fixture data or hydrate later."
} as const;

export function failStaticBackendRequest(path: string): never {
  throw new Error(
    `Static export cannot call backend endpoint '${path}'. Use fixture data or a hydrated client adapter.`
  );
}
