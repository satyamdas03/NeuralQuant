const KEY = "nq_watchlist_v1";

export function getWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
  catch { return []; }
}

export function addToWatchlist(ticker: string): void {
  const list = getWatchlist();
  if (!list.includes(ticker))
    localStorage.setItem(KEY, JSON.stringify([...list, ticker]));
}

export function removeFromWatchlist(ticker: string): void {
  localStorage.setItem(KEY, JSON.stringify(getWatchlist().filter(t => t !== ticker)));
}

export function toggleWatchlist(ticker: string): boolean {
  if (getWatchlist().includes(ticker)) { removeFromWatchlist(ticker); return false; }
  addToWatchlist(ticker); return true;
}

export function isWatchlisted(ticker: string): boolean {
  return getWatchlist().includes(ticker);
}
