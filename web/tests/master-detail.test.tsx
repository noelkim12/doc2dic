import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import MasterDetail from "../src/components/shared/MasterDetail";

describe("MasterDetail", () => {
  it("renders the list slot and the routed detail via Outlet", () => {
    render(
      <MemoryRouter initialEntries={["/x/1"]}>
        <Routes>
          <Route path="/x" element={<MasterDetail list={<div>LIST</div>} />}>
            <Route path=":id" element={<div>DETAIL</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("LIST")).toBeInTheDocument();
    expect(screen.getByText("DETAIL")).toBeInTheDocument();
  });

  it("renders the index placeholder when no child route matches", () => {
    render(
      <MemoryRouter initialEntries={["/x"]}>
        <Routes>
          <Route path="/x" element={<MasterDetail list={<div>LIST</div>} />}>
            <Route index element={<div>PLACEHOLDER</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("PLACEHOLDER")).toBeInTheDocument();
  });
});
