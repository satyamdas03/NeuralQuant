"use client";

interface Row {
  selection: string;
  universe: string;
  irs: string;
  entry: string;
  exit: string;
  returnPct: string;
  alpha: string;
  status: "BEAT" | "MISSED";
}

const ROWS: Row[] = [
  { selection: "Selection 1", universe: "SmallCap 250", irs: "94.2", entry: "₹ 342.50", exit: "₹ 441.20", returnPct: "+28.8%", alpha: "+17.5%", status: "BEAT" },
  { selection: "Selection 2", universe: "MicroCap 250", irs: "91.7", entry: "₹ 128.00", exit: "₹ 168.40", returnPct: "+31.6%", alpha: "+20.3%", status: "BEAT" },
  { selection: "Selection 3", universe: "SmallCap 250", irs: "89.4", entry: "₹ 1,845.00", exit: "₹ 2,210.50", returnPct: "+19.8%", alpha: "+8.5%", status: "BEAT" },
  { selection: "Selection 4", universe: "MicroCap 250", irs: "87.1", entry: "₹ 56.30", exit: "₹ 62.10", returnPct: "+10.3%", alpha: "-1.0%", status: "MISSED" },
  { selection: "Selection 5", universe: "SmallCap 250", irs: "93.5", entry: "₹ 678.00", exit: "₹ 892.50", returnPct: "+31.6%", alpha: "+20.3%", status: "BEAT" },
  { selection: "Selection 6", universe: "MicroCap 250", irs: "88.0", entry: "₹ 215.40", exit: "₹ 281.60", returnPct: "+30.7%", alpha: "+19.4%", status: "BEAT" },
];

export default function QuarterlyBreakdownTable() {
  return (
    <div
      className="w-full border"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-ghost-border)",
      }}
    >
      <div className="p-6 md:p-8 border-b"
        style={{ borderColor: "var(--color-ghost-border)" }}
      >
        <h3 className="font-headline text-xl md:text-2xl font-bold text-text-primary">
          Quarterly Breakdown
        </h3>
        <p className="mt-1 font-mono text-[11px] text-text-muted">
          Anonymized selections from Q1 FY2027 (Apr–Jun 2026)
        </p>
      </div>

      <div className="overflow-x-auto hide-scrollbar">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr
              className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase"
              style={{ color: "var(--color-text-muted)", background: "var(--color-surface-low)" }}
            >
              <th className="text-left px-6 py-4">Selection</th>
              <th className="text-left px-6 py-4">Universe</th>
              <th className="text-right px-6 py-4">IRS%</th>
              <th className="text-right px-6 py-4">Entry Price</th>
              <th className="text-right px-6 py-4">Exit Price</th>
              <th className="text-right px-6 py-4">Return</th>
              <th className="text-right px-6 py-4">Alpha</th>
              <th className="text-center px-6 py-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => (
              <tr
                key={row.selection}
                className="border-t transition-colors duration-200"
                style={{
                  borderColor: "var(--color-ghost-border)",
                  background: i % 2 === 0 ? "var(--color-surface)" : "var(--color-surface-low)",
                }}
              >
                <td className="px-6 py-4 font-mono text-[12px] text-text-primary font-bold">
                  {row.selection}
                </td>
                <td className="px-6 py-4 font-mono text-[12px] text-text-muted">
                  {row.universe}
                </td>
                <td className="px-6 py-4 font-mono text-[12px] text-primary text-right tabular-nums">
                  {row.irs}%
                </td>
                <td className="px-6 py-4 font-mono text-[12px] text-text-muted text-right tabular-nums">
                  {row.entry}
                </td>
                <td className="px-6 py-4 font-mono text-[12px] text-text-muted text-right tabular-nums">
                  {row.exit}
                </td>
                <td
                  className="px-6 py-4 font-mono text-[12px] font-bold text-right tabular-nums"
                  style={{ color: "var(--color-primary)" }}
                >
                  {row.returnPct}
                </td>
                <td
                  className="px-6 py-4 font-mono text-[12px] font-bold text-right tabular-nums"
                  style={{
                    color: row.status === "BEAT"
                      ? "var(--color-primary)"
                      : "var(--color-cyber-red)",
                  }}
                >
                  {row.alpha}
                </td>
                <td className="px-6 py-4 text-center">
                  <span
                    className="inline-block px-3 py-1 font-mono text-[10px] font-bold tracking-[0.1em] uppercase"
                    style={{
                      background: row.status === "BEAT"
                        ? "rgba(0, 255, 178, 0.1)"
                        : "rgba(255, 65, 88, 0.1)",
                      color: row.status === "BEAT"
                        ? "var(--color-primary)"
                        : "var(--color-cyber-red)",
                    }}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="px-6 md:px-8 py-4 border-t font-mono text-[10px] text-text-muted"
        style={{ borderColor: "var(--color-ghost-border)", background: "var(--color-surface-low)" }}
      >
        Tickers are anonymized for compliance. Full attribution available to verified subscribers.
      </div>
    </div>
  );
}
