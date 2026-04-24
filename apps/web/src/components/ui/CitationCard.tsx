type Props = {
  title: string;
  authors: string;
  year: number;
  application: string;
};

export default function CitationCard({ title, authors, year, application }: Props) {
  return (
    <div className="rounded-xl bg-surface-low/40 ghost-border p-5 hover-glow transition-colors">
      <p className="font-semibold text-on-surface text-sm">{title}</p>
      <p className="text-xs text-on-surface-variant mt-1">{authors} ({year})</p>
      <p className="text-xs text-tertiary mt-2">{application}</p>
    </div>
  );
}