interface Props {
  readonly message: string;
}

export default function EmptyState({ message }: Props) {
  return <div className="state-empty">{message}</div>;
}
