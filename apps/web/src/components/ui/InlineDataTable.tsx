type Row = Record<string, React.ReactNode>;

type Props = {
  headers: string[];
  rows: Row[];
  className?: string;
};

export default function InlineDataTable({
  headers,
  rows,
  className = "",
}: Props) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-ghost-border">
            {headers.map((h) => (
              <th
                key={h}
                className="px-2 py-1.5 text-left font-medium text-on-surface-variant"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ghost-border/50">
              {headers.map((h) => (
                <td key={h} className="px-2 py-1.5 text-on-surface">
                  {row[h] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}