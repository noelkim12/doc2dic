import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import SimilarConceptList from "../../components/search/SimilarConceptList";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { searchQueries } from "../../lib/queries";
import { ApiError } from "../../lib/api";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.body?.message || error.message;
  }
  return error instanceof Error ? error.message : "Search failed";
}

export default function SearchPage() {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState("");

  const query = useQuery(searchQueries.similar(submitted));
  const results = query.data ?? [];
  const hasSubmitted = submitted.length > 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(text.trim());
  }

  return (
    <div className="page-search">
      <header className="page-header">
        <h1 className="page-title">Vector Search</h1>
      </header>

      <form className="search-form" onSubmit={handleSubmit}>
        <label htmlFor="search-text">Search text</label>
        <textarea
          id="search-text"
          className="search-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Enter a phrase to find semantically similar terms..."
        />
        <button
          className="btn-primary"
          type="submit"
          disabled={text.trim().length === 0}
        >
          Search
        </button>
      </form>

      <section className="search-results" aria-label="Search results">
        {!hasSubmitted ? (
          <EmptyState message="Enter text and search to find similar terms." />
        ) : query.isLoading ? (
          <Loading label="Searching..." />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : results.length === 0 ? (
          <EmptyState message="No similar terms found." />
        ) : (
          <SimilarConceptList matches={results} />
        )}
      </section>
    </div>
  );
}
