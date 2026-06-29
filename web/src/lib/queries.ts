import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api";
import type {
  CreateConceptPayload,
  CreateVariantPayload,
  IssueActionRequest,
  PatchConceptPayload,
  IssueStatus,
} from "./types";

/* Re-export for convenience of mutation hook consumers */
export type {
  CreateConceptPayload,
  PatchConceptPayload,
  CreateVariantPayload,
};

type IssueActionVariables = {
  readonly id: string;
  readonly payload: IssueActionRequest;
};

export const conceptQueries = {
  all: ["concepts"] as const,
  lists: () => [...conceptQueries.all, "list"] as const,
  list: () =>
    queryOptions({
      queryKey: [...conceptQueries.lists()],
      queryFn: () => apiClient.listConcepts(),
    }),
  details: () => [...conceptQueries.all, "detail"] as const,
  detail: (id: string) =>
    queryOptions({
      queryKey: [...conceptQueries.details(), id],
      queryFn: () => apiClient.getConcept(id),
    }),
};

export const documentQueries = {
  all: ["documents"] as const,
  lists: () => [...documentQueries.all, "list"] as const,
  list: () =>
    queryOptions({
      queryKey: [...documentQueries.lists()],
      queryFn: () => apiClient.listDocuments(),
    }),
  details: () => [...documentQueries.all, "detail"] as const,
  detail: (id: string) =>
    queryOptions({
      queryKey: [...documentQueries.details(), id],
      queryFn: () => apiClient.getDocument(id),
    }),
  occurrences: (documentId: string) =>
    queryOptions({
      queryKey: [...documentQueries.all, "occurrences", documentId],
      queryFn: () => apiClient.listDocumentOccurrences(documentId),
    }),
};

export const issueQueries = {
  all: ["issues"] as const,
  lists: () => [...issueQueries.all, "list"] as const,
  list: (status?: IssueStatus) =>
    queryOptions({
      queryKey: [...issueQueries.lists(), { status }],
      queryFn: () => apiClient.listIssues(status),
    }),
  details: () => [...issueQueries.all, "detail"] as const,
  detail: (id: string) =>
    queryOptions({
      queryKey: [...issueQueries.details(), id],
      queryFn: () => apiClient.getIssue(id),
    }),
};

export const graphQueries = {
  all: ["graphs"] as const,
  current: () =>
    queryOptions({
      queryKey: [...graphQueries.all, "current"],
      queryFn: () => apiClient.getCurrentGraph(),
    }),
  snapshots: () =>
    queryOptions({
      queryKey: [...graphQueries.all, "snapshots"],
      queryFn: () => apiClient.listGraphSnapshots(),
    }),
  snapshot: (id: string) =>
    queryOptions({
      queryKey: [...graphQueries.all, "snapshot", id],
      queryFn: () => apiClient.getGraphSnapshot(id),
    }),
};

export const searchQueries = {
  all: ["search"] as const,
  similar: (text: string) =>
    queryOptions({
      queryKey: [...searchQueries.all, "similar", text] as const,
      queryFn: () => apiClient.searchSimilarConcepts(text),
      enabled: text.trim().length > 0,
    }),
};

export function useCreateConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateConceptPayload) => apiClient.createConcept(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: conceptQueries.lists() });
    },
  });
}

export function usePatchConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PatchConceptPayload }) =>
      apiClient.patchConcept(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: conceptQueries.details() });
      qc.invalidateQueries({ queryKey: conceptQueries.lists() });
    },
  });
}

export function useDeleteConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.deleteConcept(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: conceptQueries.lists() });
      qc.invalidateQueries({ queryKey: conceptQueries.details() });
    },
  });
}

export function useCreateVariant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conceptId,
      data,
    }: {
      conceptId: string;
      data: CreateVariantPayload;
    }) => apiClient.createTermVariant(conceptId, data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: [...conceptQueries.details(), variables.conceptId],
      });
    },
  });
}

/* ── Document mutations ── */

export function useAnalyzeDocumentPath() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => apiClient.analyzeDocumentPath(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: documentQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
    },
  });
}

/* ── Issue action mutations (no optimistic update -- errors must stay visible) ── */

export function useAcceptIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: IssueActionVariables) =>
      apiClient.acceptIssue(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.details() });
    },
  });
}

export function useDismissIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: IssueActionVariables) =>
      apiClient.dismissIssue(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.details() });
    },
  });
}

export function useResolveIssueAsNewConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: IssueActionVariables) =>
      apiClient.resolveIssueAsNewConcept(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.details() });
      qc.invalidateQueries({ queryKey: conceptQueries.lists() });
    },
  });
}

export function useResolveIssueAsAlias() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: IssueActionVariables) =>
      apiClient.resolveIssueAsAlias(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.details() });
    },
  });
}

export function useResolveIssueAsForbidden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: IssueActionVariables) =>
      apiClient.resolveIssueAsForbidden(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: issueQueries.lists() });
      qc.invalidateQueries({ queryKey: issueQueries.details() });
    },
  });
}
