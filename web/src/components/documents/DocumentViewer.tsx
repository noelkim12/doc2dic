import type { Document, DocumentChunk } from "../../lib/types";

interface Props {
  document: Document;
  chunks?: readonly DocumentChunk[];
}

function mimeTypeLabel(mime: Document["mimeType"]): string {
  const map: Record<Document["mimeType"], string> = {
    "text/markdown": "Markdown",
    "text/plain": "Plain Text",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
      "DOCX",
  };
  return map[mime] || mime;
}

export default function DocumentViewer({ document, chunks }: Props) {
  return (
    <div className="document-viewer">
      <header className="document-viewer-header">
        <h2 className="document-title">{document.title}</h2>
        <div className="document-meta">
          <span className="type-badge">{mimeTypeLabel(document.mimeType)}</span>
          <span className="text-muted document-path">{document.path}</span>
        </div>
        {document.analyzedAt && (
          <p className="text-muted document-analyzed">
            Analyzed: {new Date(document.analyzedAt).toLocaleString()}
          </p>
        )}
      </header>

      {chunks && chunks.length > 0 && (
        <section className="document-chunks" aria-label="Document sections">
          <h3 className="section-label">Sections ({chunks.length})</h3>
          <ul className="chunk-list">
            {chunks.map((chunk) => (
              <li key={chunk.id} className="chunk-item">
                <span className="chunk-ordinal">#{chunk.ordinal}</span>
                {chunk.sectionTitle && (
                  <span className="chunk-title">{chunk.sectionTitle}</span>
                )}
                <span className="chunk-preview text-muted">
                  {chunk.textPreview.slice(0, 200)}
                  {chunk.textPreview.length > 200 ? "..." : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
