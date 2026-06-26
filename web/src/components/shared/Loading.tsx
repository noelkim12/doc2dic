interface Props {
  readonly label?: string;
}

export default function Loading({ label = "Loading..." }: Props) {
  return <div className="state-loading">{label}</div>;
}
