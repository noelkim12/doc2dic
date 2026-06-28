import { Outlet, Routes, Route, NavLink } from "react-router-dom";
import HomePage from "./page";
import GlossaryPage from "./glossary/page";
import ConceptDetailPage from "./glossary/[conceptId]/page";
import DocumentsPage from "./documents/page";
import DocumentDetailPage from "./documents/[documentId]/page";
import ReviewPage from "./review/page";
import IssueDetailPage from "./review/[issueId]/page";
import GraphPage from "./graph/page";
import SearchPage from "./search/page";
import SettingsPage from "./settings/page";
import EmptyState from "../components/shared/EmptyState";

const NAV_ITEMS = [
  { to: "/", label: "Home" },
  { to: "/glossary", label: "Glossary" },
  { to: "/documents", label: "Documents" },
  { to: "/review", label: "Review" },
  { to: "/graph", label: "Graph" },
  { to: "/search", label: "Vector Search" },
  { to: "/settings", label: "Settings" },
] as const;

export default function AppLayout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <h1 className="app-brand">Doc2Dic</h1>
        <ul className="app-nav-list">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/" ? true : undefined}
                className={({ isActive }) =>
                  isActive ? "active" : undefined
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="app-main">
        <Routes>
          <Route index element={<HomePage />} />
          <Route path="glossary" element={<GlossaryPage />}>
            <Route
              index
              element={
                <EmptyState message="Select a term to view its definition." />
              }
            />
            <Route path=":conceptId" element={<ConceptDetailPage />} />
          </Route>
          <Route path="documents" element={<DocumentsPage />}>
            <Route
              index
              element={
                <EmptyState message="Select a document to view its contents." />
              }
            />
            <Route path=":documentId" element={<DocumentDetailPage />} />
          </Route>
          <Route path="review" element={<ReviewPage />}>
            <Route
              index
              element={
                <EmptyState message="Select an issue to review its details and actions." />
              }
            />
            <Route path=":issueId" element={<IssueDetailPage />} />
          </Route>
          <Route path="graph" element={<GraphPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Routes>
        <Outlet />
      </main>
    </div>
  );
}
