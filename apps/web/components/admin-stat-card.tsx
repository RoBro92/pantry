type AdminStatCardProps = {
  label: string;
  value: number;
  detail: string;
};

export function AdminStatCard({ label, value, detail }: AdminStatCardProps) {
  return (
    <article className="status-card">
      <p className="eyebrow">{label}</p>
      <h2>{value}</h2>
      <p>{detail}</p>
    </article>
  );
}

