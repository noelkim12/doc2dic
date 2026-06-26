interface Props {
  text: string;
  surface: string;
}

export default function HighlightedText({ text, surface }: Props) {
  const parts = text.split(surface);
  return (
    <span>
      {parts.map((part, i) =>
        i < parts.length - 1 ? (
          <span key={i}>
            {part}
            <mark>{surface}</mark>
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </span>
  );
}
