import type {
  Concept,
  SimilarConceptMatch,
  TermVariant,
  Document,
  TermOccurrence,
  TermIssue,
  IssueActionPayload,
  IssueActionRequest,
  AppGraph,
  GraphSnapshot,
  GraphifyProjection,
  CreateConceptPayload,
  PatchConceptPayload,
  CreateVariantPayload,
} from "./types";

const BASE = "/api";

export const API_ENDPOINTS = {
  health: `${BASE}/health`,
  concepts: `${BASE}/concepts`,
  concept: (id: string) => `${BASE}/concepts/${id}`,
  conceptVariants: (id: string) => `${BASE}/concepts/${id}/variants`,
  variant: (id: string) => `${BASE}/variants/${id}`,
  documents: `${BASE}/documents`,
  document: (id: string) => `${BASE}/documents/${id}`,
  documentOccurrences: (id: string) => `${BASE}/documents/${id}/occurrences`,
  analyzePath: `${BASE}/documents/analyze-path`,
  issues: `${BASE}/issues`,
  issue: (id: string) => `${BASE}/issues/${id}`,
  issueAccept: (id: string) => `${BASE}/issues/${id}/accept`,
  issueDismiss: (id: string) => `${BASE}/issues/${id}/dismiss`,
  issueResolveNewConcept: (id: string) =>
    `${BASE}/issues/${id}/resolve-as-new-concept`,
  issueResolveAlias: (id: string) => `${BASE}/issues/${id}/resolve-as-alias`,
  issueResolveForbidden: (id: string) =>
    `${BASE}/issues/${id}/resolve-as-forbidden`,
  searchConcepts: `${BASE}/search/concepts`,
  searchSimilarConcepts: `${BASE}/search/similar-concepts`,
  currentGraph: `${BASE}/graphs/current`,
  rebuildGraph: `${BASE}/graphs/rebuild`,
  graphSnapshots: `${BASE}/graphs/snapshots`,
  graphSnapshot: (id: string) => `${BASE}/graphs/snapshots/${id}`,
  exportGraphify: `${BASE}/graphs/graphify/export`,
} as const;

export type SafeErrorBody = {
  readonly message?: string;
  readonly code?: string;
  readonly details?: string;
} | null;

const MAX_DETAILS_LENGTH = 500;

function safeBody(raw: unknown): SafeErrorBody {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const root = raw as Record<string, unknown>;
  const obj =
    root.error !== null &&
    typeof root.error === "object" &&
    !Array.isArray(root.error)
      ? (root.error as Record<string, unknown>)
      : root;
  return {
    message: typeof obj.message === "string" ? obj.message : undefined,
    code: typeof obj.code === "string" ? obj.code : undefined,
    details:
      typeof obj.details === "string"
        ? String(obj.details).slice(0, MAX_DETAILS_LENGTH)
        : undefined,
  };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    rawBody?: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = "ApiError";
    Object.defineProperty(this, "body", {
      value: safeBody(rawBody),
      writable: false,
      enumerable: true,
      configurable: false,
    });
  }

  declare readonly body: SafeErrorBody;

  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

async function throwOnError(res: Response): Promise<Response> {
  if (!res.ok) {
    let parsed: unknown = null;
    try {
      parsed = await res.json();
    } catch {
      throw new ApiError(res.status, res.statusText, null);
    }
    throw new ApiError(res.status, res.statusText, safeBody(parsed));
  }
  return res;
}

const DEFAULT_INIT: RequestInit = {
  headers: { "Content-Type": "application/json" },
};

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  await throwOnError(res);
  return res.json() as Promise<T>;
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    ...DEFAULT_INIT,
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
  await throwOnError(res);
  return res.json() as Promise<T>;
}

async function patch<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    ...DEFAULT_INIT,
    method: "PATCH",
    body: JSON.stringify(body),
  });
  await throwOnError(res);
  return res.json() as Promise<T>;
}

async function del(url: string): Promise<void> {
  const res = await fetch(url, { method: "DELETE" });
  await throwOnError(res);
}

export const apiClient = {
  health(): Promise<void> {
    return get(API_ENDPOINTS.health);
  },

  listConcepts(): Promise<readonly Concept[]> {
    return get(API_ENDPOINTS.concepts);
  },

  getConcept(id: string): Promise<Concept> {
    return get(API_ENDPOINTS.concept(id));
  },

  createConcept(data: CreateConceptPayload): Promise<Concept> {
    return post(API_ENDPOINTS.concepts, data);
  },

  patchConcept(id: string, data: PatchConceptPayload): Promise<Concept> {
    return patch(API_ENDPOINTS.concept(id), data);
  },

  deleteConcept(id: string): Promise<void> {
    return del(API_ENDPOINTS.concept(id));
  },

  createTermVariant(
    conceptId: string,
    data: CreateVariantPayload,
  ): Promise<TermVariant> {
    return post(API_ENDPOINTS.conceptVariants(conceptId), data);
  },

  patchTermVariant(
    id: string,
    data: Partial<Pick<TermVariant, "label" | "variantType" | "status">>,
  ): Promise<TermVariant> {
    return patch(API_ENDPOINTS.variant(id), data);
  },

  deleteTermVariant(id: string): Promise<void> {
    return del(API_ENDPOINTS.variant(id));
  },

  analyzeDocumentPath(path: string): Promise<void> {
    return post(API_ENDPOINTS.analyzePath, { path });
  },

  listDocuments(): Promise<readonly Document[]> {
    return get(API_ENDPOINTS.documents);
  },

  getDocument(id: string): Promise<Document> {
    return get(API_ENDPOINTS.document(id));
  },

  listDocumentOccurrences(id: string): Promise<readonly TermOccurrence[]> {
    return get(API_ENDPOINTS.documentOccurrences(id));
  },

  listIssues(status?: TermIssue["status"]): Promise<readonly TermIssue[]> {
    const url = status
      ? `${API_ENDPOINTS.issues}?status=${status}`
      : API_ENDPOINTS.issues;
    return get(url);
  },

  getIssue(id: string): Promise<TermIssue> {
    return get(API_ENDPOINTS.issue(id));
  },

  acceptIssue(id: string, data: IssueActionRequest): Promise<IssueActionPayload> {
    return post<IssueActionPayload>(API_ENDPOINTS.issueAccept(id), data);
  },

  dismissIssue(id: string, data: IssueActionRequest): Promise<IssueActionPayload> {
    return post<IssueActionPayload>(API_ENDPOINTS.issueDismiss(id), data);
  },

  resolveIssueAsNewConcept(
    id: string,
    data: IssueActionRequest,
  ): Promise<IssueActionPayload> {
    return post<IssueActionPayload>(API_ENDPOINTS.issueResolveNewConcept(id), data);
  },

  resolveIssueAsAlias(
    id: string,
    data: IssueActionRequest,
  ): Promise<IssueActionPayload> {
    return post<IssueActionPayload>(API_ENDPOINTS.issueResolveAlias(id), data);
  },

  resolveIssueAsForbidden(
    id: string,
    data: IssueActionRequest,
  ): Promise<IssueActionPayload> {
    return post<IssueActionPayload>(API_ENDPOINTS.issueResolveForbidden(id), data);
  },

  searchConcepts(q: string): Promise<readonly Concept[]> {
    return get(`${API_ENDPOINTS.searchConcepts}?q=${encodeURIComponent(q)}`);
  },

  searchSimilarConcepts(text: string): Promise<readonly SimilarConceptMatch[]> {
    return get(
      `${API_ENDPOINTS.searchSimilarConcepts}?text=${encodeURIComponent(text)}`,
    );
  },

  getCurrentGraph(): Promise<AppGraph> {
    return get(API_ENDPOINTS.currentGraph);
  },

  rebuildGraph(): Promise<void> {
    return post(API_ENDPOINTS.rebuildGraph);
  },

  listGraphSnapshots(): Promise<readonly GraphSnapshot[]> {
    return get(API_ENDPOINTS.graphSnapshots);
  },

  getGraphSnapshot(id: string): Promise<GraphSnapshot> {
    return get(API_ENDPOINTS.graphSnapshot(id));
  },

  exportGraphify(): Promise<GraphifyProjection> {
    return post(API_ENDPOINTS.exportGraphify);
  },
} as const;
