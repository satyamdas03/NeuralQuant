type Props = {
  title: string;
  authors: string;
  year: number;
  application: string;
};

export default function CitationCard({ title, authors, year, application }: Props) {
  return (
    <div className="glass border border-border-glow p-5 hover:shadow-[0_0_20px_rgba(0,255,178,0.15)] hover:border-primary-fixed/40 transition-all duration-300">
      <p className="font-headline font-bold text-primary text-sm">{title}</p>
      <p className="font-mono text-[11px] text-text-muted mt-1 tracking-[0.1em] uppercase">
        {authors} ({year})
      </p>
      <p className="font-mono text-[11px] text-tertiary-fixed-dim mt-2 tracking-[0.1em]">
        {application}
      </p>
    </div>
  );
}
