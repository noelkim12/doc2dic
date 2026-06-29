import { useState, useId } from "react";
import type { Concept, TermType } from "../../lib/types";
import TagInput from "../shared/TagInput";
import type { ApiError } from "../../lib/api";

interface FormData {
  primaryTerm: string;
  definition: string;
  termType: TermType;
  status: Concept["status"];
  tags: readonly string[];
  physicalName: string;
}

const EMPTY_FORM: FormData = {
  primaryTerm: "",
  definition: "",
  termType: "unknown" as TermType,
  status: "active",
  tags: [],
  physicalName: "",
};

function formFromConcept(c: Concept): FormData {
  return {
    primaryTerm: c.primaryTerm,
    definition: c.definition,
    termType: c.termType,
    status: c.status,
    tags: [...c.tags],
    physicalName: c.physicalName ?? "",
  };
}

interface Props {
  concept?: Concept;
  onSubmit: (data: FormData) => void | Promise<void>;
  isSubmitting?: boolean;
  error?: ApiError | null;
}

const TERM_TYPES: readonly TermType[] = [
  "mechanic",
  "resource",
  "state",
  "action",
  "stat",
  "entity",
  "rule",
  "ui-label",
  "lore",
  "unknown",
];

export default function ConceptForm({
  concept,
  onSubmit,
  isSubmitting = false,
  error,
}: Props) {
  const [form, setForm] = useState<FormData>(
    concept ? formFromConcept(concept) : EMPTY_FORM,
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const groupId = useId();

  const isEdit = !!concept;

  function update<K extends keyof FormData>(key: K, value: FormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFieldErrors({});

    const errors: Record<string, string> = {};
    if (!form.primaryTerm.trim()) errors.primaryTerm = "Primary term is required.";
    if (!form.definition.trim()) errors.definition = "Definition is required.";

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    try {
      await onSubmit(form);
      if (!isEdit) setForm(EMPTY_FORM);
    } catch {
      // Preserve form state on failure -- key requirement
    }
  }

  // Extract inline validation message from API error body
  const apiDetail = error?.body?.details || error?.body?.message;

  return (
    <form
      className="concept-form"
      onSubmit={handleSubmit}
      aria-label={isEdit ? "Edit concept" : "Create new concept"}
    >
      <fieldset className="concept-form-fieldset">
        <legend className="concept-form-legend">
          {isEdit ? "Edit Concept" : "New Concept"}
        </legend>

        <div className="field-group">
          <label htmlFor={`${groupId}-term`} className="field-label">
            Primary Term
          </label>
          <input
            id={`${groupId}-term`}
            className="field-input"
            type="text"
            value={form.primaryTerm}
            onChange={(e) => update("primaryTerm", e.target.value)}
            placeholder="e.g. 스태미나"
            autoComplete="off"
          />
          {fieldErrors.primaryTerm && (
            <span className="field-error">{fieldErrors.primaryTerm}</span>
          )}
        </div>

        <div className="field-group">
          <label htmlFor={`${groupId}-def`} className="field-label">
            Definition
          </label>
          <textarea
            id={`${groupId}-def`}
            className="field-input field-textarea"
            value={form.definition}
            onChange={(e) => update("definition", e.target.value)}
            rows={3}
            placeholder="Describe this concept..."
          />
          {fieldErrors.definition && (
            <span className="field-error">{fieldErrors.definition}</span>
          )}
        </div>

        <div className="field-row">
          <div className="field-group">
            <label htmlFor={`${groupId}-type`} className="field-label">
              Type
            </label>
            <select
              id={`${groupId}-type`}
              className="field-input field-select"
              value={form.termType}
              onChange={(e) =>
                update("termType", e.target.value as TermType)
              }
            >
              {TERM_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor={`${groupId}-status`} className="field-label">
              Status
            </label>
            <select
              id={`${groupId}-status`}
              className="field-input field-select"
              value={form.status}
              onChange={(e) =>
                update(
                  "status",
                  e.target.value as Concept["status"],
                )
              }
            >
              <option value="active">Active</option>
              <option value="deprecated">Deprecated</option>
              <option value="forbidden">Forbidden</option>
            </select>
          </div>
        </div>

        <div className="field-group">
          <span className="field-label">Tags</span>
          <TagInput
            tags={form.tags}
            onAdd={(tag) =>
              update("tags", [...form.tags, tag])
            }
            onRemove={(tag) =>
              update(
                "tags",
                form.tags.filter((t) => t !== tag),
              )
            }
          />
        </div>

        <div className="field-group">
          <label htmlFor={`${groupId}-physical`} className="field-label">
            Physical Name (물리명)
          </label>
          <input
            id={`${groupId}-physical`}
            className="field-input"
            type="text"
            value={form.physicalName}
            onChange={(e) => update("physicalName", e.target.value)}
            placeholder="e.g. hp"
            autoComplete="off"
          />
        </div>

        {apiDetail && (
          <div className="api-validation-error" role="alert">
            {apiDetail}
          </div>
        )}

        <div className="field-actions">
          <button
            type="submit"
            className="btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : isEdit ? "Update" : "Create"}
          </button>
        </div>
      </fieldset>
    </form>
  );
}
