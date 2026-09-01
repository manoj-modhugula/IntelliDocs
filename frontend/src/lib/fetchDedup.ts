/**
 * Request deduplication: in-flight requests for the same key share one promise.
 * Prevents duplicate API calls when multiple components fetch the same data.
 *
 * Each caller gets its own Response clone so `.json()` / `.text()` can be
 * called independently without "body already consumed" errors.
 */
const inFlight = new Map<string, Promise<Response>>();

export function fetchWithDedup(
  url: string,
  options?: RequestInit,
  dedupKey?: string
): Promise<Response> {
  const key = dedupKey ?? `${url}:${options?.method ?? 'GET'}:${JSON.stringify(options?.headers ?? {})}`;
  const existing = inFlight.get(key);
  if (existing) return existing.then((res) => res.clone());
  const promise = fetch(url, options).finally(() => inFlight.delete(key));
  inFlight.set(key, promise);
  // Return a clone so the original stored in the map stays unconsumed for later callers
  return promise.then((res) => res.clone());
}
