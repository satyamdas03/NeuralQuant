"use client";

import { useState } from "react";

interface BrokerPageClientProps {
  email: string;
  tier: string;
}

interface AccountInfo {
  id?: string;
  status?: string;
  currency?: string;
  buying_power?: string;
  cash?: string;
  portfolio_value?: string;
  equity?: string;
  daytrade_count?: number;
  pattern_day_trader?: boolean;
  paper?: boolean;
  error?: string;
}

interface Position {
  symbol: string;
  qty: string;
  market_value: string;
  unrealized_pl: string;
  unrealized_plpc: string;
  current_price: string;
  avg_entry_price: string;
  side: string;
}

export default function BrokerPageClient({ email: _email, tier: _tier }: BrokerPageClientProps) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [broker, setBroker] = useState<"alpaca" | "zerodha">("alpaca");
  const [deepLink, setDeepLink] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [accountLoading, setAccountLoading] = useState(false);

  const getDeepLink = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/broker/deep-link`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
        },
        body: JSON.stringify({ symbol: symbol.toUpperCase(), side, broker }),
      });
      const data = await res.json();
      if (data.url) setDeepLink(data.url);
    } catch {
      setDeepLink(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchAccount = async () => {
    setAccountLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/broker/account`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
      });
      if (res.ok) setAccount(await res.json());
      else setAccount({ error: "Alpaca not configured. Set API keys in environment." });
    } catch {
      setAccount({ error: "Failed to connect to broker." });
    } finally {
      setAccountLoading(false);
    }
  };

  const fetchPositions = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/broker/positions`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
      });
      if (res.ok) setPositions(await res.json());
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a14] text-white p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-2 bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] bg-clip-text text-transparent">
        Broker Connect
      </h1>
      <p className="text-[#a0a0b0] mb-6 text-sm">
        Open a trade ticket in your broker app. NeuralQuant never holds funds or executes orders.
      </p>

      {/* Deep Link Trade */}
      <div className="bg-[#131322] rounded-xl p-6 border border-[#1e1e30] mb-6">
        <h2 className="text-lg font-semibold mb-4">Quick Trade</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-[#a0a0b0] mb-1">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. AAPL"
              className="bg-[#0a0a14] border border-[#1e1e30] rounded-lg px-3 py-2 text-sm w-32 focus:border-[#c1c1ff] outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-[#a0a0b0] mb-1">Side</label>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
              className="bg-[#0a0a14] border border-[#1e1e30] rounded-lg px-3 py-2 text-sm focus:border-[#c1c1ff] outline-none"
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-[#a0a0b0] mb-1">Broker</label>
            <select
              value={broker}
              onChange={(e) => setBroker(e.target.value as "alpaca" | "zerodha")}
              className="bg-[#0a0a14] border border-[#1e1e30] rounded-lg px-3 py-2 text-sm focus:border-[#c1c1ff] outline-none"
            >
              <option value="alpaca">Alpaca (US)</option>
              <option value="zerodha">Zerodha (India)</option>
            </select>
          </div>
          <button
            onClick={getDeepLink}
            disabled={!symbol.trim() || loading}
            className="px-4 py-2 bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0e0e0e] rounded-lg font-semibold text-sm disabled:opacity-50 hover:opacity-90"
          >
            {loading ? "..." : "Open Trade Ticket"}
          </button>
        </div>
        {deepLink && (
          <div className="mt-4 p-3 bg-[#0a0a14] rounded-lg border border-[#1e1e30]">
            <p className="text-xs text-[#a0a0b0] mb-1">Trade ticket URL:</p>
            <a href={deepLink} target="_blank" rel="noopener noreferrer" className="text-[#bdf4ff] text-sm break-all hover:underline">
              {deepLink}
            </a>
          </div>
        )}
      </div>

      {/* Alpaca Account */}
      <div className="bg-[#131322] rounded-xl p-6 border border-[#1e1e30] mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Alpaca Account</h2>
          <button
            onClick={() => { fetchAccount(); fetchPositions(); }}
            disabled={accountLoading}
            className="text-xs px-3 py-1 border border-[#c1c1ff] text-[#c1c1ff] rounded-lg hover:bg-[#c1c1ff] hover:text-[#0e0e0e] disabled:opacity-50"
          >
            {accountLoading ? "..." : "Refresh"}
          </button>
        </div>
        {account && (
          account.error ? (
            <p className="text-sm text-[#f87171]">{account.error}</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              {account.status && <div><span className="text-[#a0a0b0]">Status</span><br/><span className="font-semibold">{account.status}</span></div>}
              {account.equity && <div><span className="text-[#a0a0b0]">Equity</span><br/><span className="font-semibold">${parseFloat(account.equity).toLocaleString()}</span></div>}
              {account.buying_power && <div><span className="text-[#a0a0b0]">Buying Power</span><br/><span className="font-semibold">${parseFloat(account.buying_power).toLocaleString()}</span></div>}
              {account.cash && <div><span className="text-[#a0a0b0]">Cash</span><br/><span className="font-semibold">${parseFloat(account.cash).toLocaleString()}</span></div>}
              {account.paper !== undefined && <div><span className="text-[#a0a0b0]">Mode</span><br/><span className="font-semibold">{account.paper ? "Paper" : "Live"}</span></div>}
            </div>
          )
        )}
        {!account && !accountLoading && (
          <p className="text-sm text-[#a0a0b0]">Click Refresh to load your Alpaca account info.</p>
        )}
      </div>

      {/* Positions */}
      {positions.length > 0 && (
        <div className="bg-[#131322] rounded-xl p-6 border border-[#1e1e30]">
          <h2 className="text-lg font-semibold mb-4">Positions</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#a0a0b0] border-b border-[#1e1e30]">
                  <th className="text-left py-2">Symbol</th>
                  <th className="text-right py-2">Qty</th>
                  <th className="text-right py-2">Value</th>
                  <th className="text-right py-2">P&L</th>
                  <th className="text-right py-2">P&L %</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.symbol} className="border-b border-[#1e1e30]">
                    <td className="py-2 font-semibold text-[#c1c1ff]">{p.symbol}</td>
                    <td className="text-right py-2">{p.qty}</td>
                    <td className="text-right py-2">${parseFloat(p.market_value).toLocaleString()}</td>
                    <td className={`text-right py-2 ${parseFloat(p.unrealized_pl) >= 0 ? "text-[#4ade80]" : "text-[#f87171]"}`}>
                      ${parseFloat(p.unrealized_pl).toFixed(2)}
                    </td>
                    <td className={`text-right py-2 ${parseFloat(p.unrealized_plpc) >= 0 ? "text-[#4ade80]" : "text-[#f87171]"}`}>
                      {(parseFloat(p.unrealized_plpc) * 100).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-6 p-4 bg-[#131322] rounded-xl border border-[#1e1e30] text-xs text-[#a0a0b0]">
        <strong>Disclaimer:</strong> NeuralQuant provides analysis and trade suggestions only. We never hold funds, route orders, or execute trades.
        Always do your own research. This is not investment advice.
      </div>
    </div>
  );
}