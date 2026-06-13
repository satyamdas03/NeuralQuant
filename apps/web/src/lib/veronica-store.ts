"use client";

import { useSyncExternalStore } from "react";

type VeronicaExternalState = {
  /** QuantAstra call modal is open — Veronica must go quiet. */
  astraOpen: boolean;
  /** Key numbers visible on the current page, for Veronica grounding. */
  pageData: Record<string, unknown> | null;
};

let state: VeronicaExternalState = { astraOpen: false, pageData: null };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export function setAstraOpen(open: boolean) {
  if (state.astraOpen === open) return;
  state = { ...state, astraOpen: open };
  emit();
}

export function setVeronicaPageData(data: Record<string, unknown> | null) {
  state = { ...state, pageData: data };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): VeronicaExternalState {
  return state;
}

const serverSnapshot: VeronicaExternalState = { astraOpen: false, pageData: null };

export function useVeronicaExternalState(): VeronicaExternalState {
  return useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
}

/** Routes where Veronica yields the floor (Ask Morgan). */
export function isQuietRoute(pathname: string): boolean {
  return pathname.startsWith("/query");
}
