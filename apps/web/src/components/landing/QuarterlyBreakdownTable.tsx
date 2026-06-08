"use client";

interface PoolRow {
  pool: string;
  count: number;
  avg_return: number;
  avg_benchmark: number;
  alpha: number;
  hit_rate: number;
}

function EmptyState() {
  return (
    <div className="w-full border flex flex-col items-center justify-center gap-3 py-12" style={{ background: "var(--color-surface)", borderColor: "var(--color-ghost-border)" }}>
      <p className="font-mono text-[11px] text-text-muted">Quarterly breakdown available after evaluation</p>
    </div>
  );
}

export default function QuarterlyBreakdownTable({
  breakdown,
}: {
  breakdown?: Array<PoolRow> | null;
}) {
  const hasData = breakdown && breakdown.length > 0;

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
          Pool-level results from Q1 FY2027 (Apr–Jun 2026)
        </p>
      </div>

      {!hasData ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto hide-scrollbar">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr
                className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase"
                style={{ color: "var(--color-text-muted)", background: "var(--color-surface-low)" }}
              >
                <th className="text-left px-6 py-4">Pool</th>
                <th className="text-right px-6 py-4">Selections</th>
                <th className="text-right px-6 py-4">Avg Return</th>
                <th className="text-right px-6 py-4">Benchmark</th>
                <th className="text-right px-6 py-4">Alpha</th>
                <th className="text-right px-6 py-4">Hit Rate</th>
                <th className="text-center px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {breakdown!.map((row, i) => {
                const status = row.alpha > 0 ? "BEAT" : "MISSED";
                return (
                  <tr
                    key={row.pool}
                    className="border-t transition-colors duration-200"
                    style={{
                      borderColor: "var(--color-ghost-border)",
                      background: i % 2 === 0 ? "var(--color-surface)" : "var(--color-surface-low)",
                    }}
                  >
                    <td className="px-6 py-4 font-mono text-[12px] text-text-primary font-bold">
                      {row.pool}
                    </td>
                    <td className="px-6 py-4 font-mono text-[12px] text-text-muted text-right tabular-nums">
                      {row.count}
                    </td>
                    <td
                      className="px-6 py-4 font-mono text-[12px] font-bold text-right tabular-nums"
                      style={{ color: "var(--color-primary)" }}
                    >
                      +{row.avg_return.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 font-mono text-[12px] text-text-muted text-right tabular-nums">
                      +{row.avg_benchmark.toFixed(1)}%
                    </td>
                    <td
                      className="px-6 py-4 font-mono text-[12px] font-bold text-right tabular-nums"
                      style={{
                        color: row.alpha >= 0 ? "var(--color-primary)" : "var(--color-cyber-red)",
                      }}
                    >
                      {row.alpha >= 0 ? "+" : ""}{row.alpha.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 font-mono text-[12px] text-text-muted text-right tabular-nums">
                      {row.hit_rate.toFixed(0)}%
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className="inline-block px-3 py-1 font-mono text-[10px] font-bold tracking-[0.1em] uppercase"
                        style={{
                          background: status === "BEAT"
                            ? "rgba(0, 255, 178, 0.1)"
                            : "rgba(255, 65, 88, 0.1)",
                          color: status === "BEAT"
                            ? "var(--color-primary)"
                            : "var(--color-cyber-red)",
                        }}
                      >
                        {status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div
        className="px-6 md:px-8 py-4 border-t font-mono text-[10px] text-text-muted"
        style={{ borderColor: "var(--color-ghost-border)", background: "var(--color-surface-low)" }}
      >
        Results are anonymized at the pool level for compliance. Individual attribution available to verified subscribers.
      </div>
    </div>
  );
}
