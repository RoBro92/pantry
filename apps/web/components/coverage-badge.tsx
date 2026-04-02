type CoverageBadgeProps = {
  status: "fully_covered" | "partially_covered" | "missing";
};

const LABELS: Record<CoverageBadgeProps["status"], string> = {
  fully_covered: "Fully covered",
  partially_covered: "Partially covered",
  missing: "Missing"
};

export function CoverageBadge({ status }: CoverageBadgeProps) {
  return <span className={`coverage-badge coverage-${status}`}>{LABELS[status]}</span>;
}
