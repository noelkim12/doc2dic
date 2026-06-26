interface Props {
  confidence: number;
}

export default function ConfidenceBadge({ confidence }: Props) {
  const level = confidence >= 0.9 ? "high" : confidence >= 0.7 ? "medium" : "low";
  return <span className={`confidence confidence-${level}`}>{confidence.toFixed(2)}</span>;
}
