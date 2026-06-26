interface Props {
  readonly message: string;
  readonly onRetry?: () => void;
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="state-error">
      <p>{message}</p>
      {onRetry && <button onClick={onRetry} type="button">Retry</button>}
    </div>
  );
}
