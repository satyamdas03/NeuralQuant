/** Zustand store — auth, portfolio, risk profile state. */

import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { fetchWatchlist, fetchPortfolioAssess } from '../services/api';

// ── Global type for auth token ────────────────────────────────────────
declare global {
  var __NQ_AUTH_TOKEN: string | null;
}

interface AuthState {
  userId: string | null;
  email: string | null;
  isSignedIn: boolean;
  setAuth: (userId: string | null, email: string | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  email: null,
  isSignedIn: false,
  setAuth: (userId, email) => set({ userId, email, isSignedIn: !!userId }),
  clear: () => set({ userId: null, email: null, isSignedIn: false }),
}));

interface RiskProfileState {
  riskProfile: 'low' | 'high' | 'very_high' | null;
  setRiskProfile: (profile: 'low' | 'high' | 'very_high') => void;
  loadSavedProfile: () => Promise<void>;
}

export const useRiskProfileStore = create<RiskProfileState>((set) => ({
  riskProfile: null,
  setRiskProfile: (profile) => {
    set({ riskProfile: profile });
    SecureStore.setItemAsync('astra_risk_profile', profile);
  },
  loadSavedProfile: async () => {
    const saved = await SecureStore.getItemAsync('astra_risk_profile');
    if (saved && ['low', 'high', 'very_high'].includes(saved)) {
      set({ riskProfile: saved as 'low' | 'high' | 'very_high' });
    }
  },
}));

interface PortfolioState {
  holdings: any[];
  isLoading: boolean;
  setHoldings: (stocks: any[]) => void;
  setLoading: (loading: boolean) => void;
  fetchHoldings: () => Promise<void>;
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
  holdings: [],
  isLoading: false,
  setHoldings: (stocks) => set({ holdings: stocks, isLoading: false }),
  setLoading: (loading) => set({ isLoading: loading }),
  fetchHoldings: async () => {
    set({ isLoading: true });
    try {
      const watchlist = await fetchWatchlist();
      const items = watchlist?.items || [];
      if (items.length === 0) {
        set({ holdings: [], isLoading: false });
        return;
      }
      const holdingsPayload = items.map((item: any) => ({
        ticker: item.ticker,
        market: item.market || 'US',
      }));
      const assessment = await fetchPortfolioAssess(holdingsPayload);
      set({ holdings: assessment?.holdings || [], isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },
}));