import { useState } from "react";

interface Props {
  onAnalyze: (path: string) => void | Promise<void>;
  isAnalyzing?: boolean;
  error?: string | null;
}

export default function DocumentUploader({
  onAnalyze,
  isAnalyzing = false,
  error,
}: Props) {
  const [path, setPath] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = path.trim();
    if (!trimmed) return;
    await onAnalyze(trimmed);
    // Keep path visible after submission so user can see what was analyzed
  }

  return (
    <form
      className="document-uploader"
      onSubmit={handleSubmit}
      aria-label="Analyze document path"
    >
      <div className="uploader-field">
        <label htmlFor="doc-path-input" className="field-label">
          Document Path
        </label>
        <input
          id="doc-path-input"
          className="field-input"
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="e.g. samples/docs/combat_core.md"
          disabled={isAnalyzing}
          autoComplete="off"
        />
      </div>
      <button
        type="submit"
        className="btn-primary btn-sm"
        disabled={isAnalyzing || !path.trim()}
      >
        {isAnalyzing ? "Analyzing..." : "Analyze"}
      </button>
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </form>
  );
}
