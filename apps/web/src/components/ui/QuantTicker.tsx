type Props = {
  ticker: string;
  price: number;
  changePct: number;
  currency?: string;
};

export default function QuantTicker({
  ticker,
  price,
  changePct,
  currency = "$",
}: Props) {
  const up = changePct >= 0;

  return (
    <div className="flex items-baseline gap-3">
      <span className="font-headline text-lg font-bold text-on-surface">
        {ticker}
      </span>
      <span className="tabular-nums text-sm text-on-surface">
        {currency}{price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span
        className={`tabular-nums text-xs font-medium ${
          up ? "text-tertiary" : "text-error"
        }`}
      >
        {up ? "+" : ""}{changePct.toFixed(2)}%
      </span>
    </div>
  );
}