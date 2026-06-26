interface Props {
  tags: readonly string[];
  onAdd?: (tag: string) => void;
  onRemove?: (tag: string) => void;
}

export default function TagInput({ tags, onAdd, onRemove }: Props) {
  return (
    <div className="tag-input">
      <ul>
        {tags.map((tag) => (
          <li key={tag}>
            {tag}
            {onRemove && (
              <button type="button" onClick={() => onRemove(tag)}>
                x
              </button>
            )}
          </li>
        ))}
      </ul>
      <div className="tag-input-row">
        <input name="newTag" onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            const val = (e.target as HTMLInputElement).value;
            if (val) { onAdd?.(val); (e.target as HTMLInputElement).value = ""; }
          }
        }} />
        <button type="button" onClick={(e) => {
          const input = (e.currentTarget.previousElementSibling as HTMLInputElement);
          const val = input?.value;
          if (val) { onAdd?.(val); if (input) input.value = ""; }
        }}>Add</button>
      </div>
    </div>
  );
}
