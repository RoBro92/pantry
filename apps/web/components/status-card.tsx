type StatusCardProps = {
  title: string;
  value: string;
  detail: string;
};

export function StatusCard({ title, value, detail }: StatusCardProps) {
  return (
    <section className="status-card">
      <p className="eyebrow">{title}</p>
      <h2>{value}</h2>
      <p>{detail}</p>
    </section>
  );
}

