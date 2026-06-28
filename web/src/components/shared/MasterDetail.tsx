import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

interface Props {
  readonly list: ReactNode;
}

/**
 * Three-pane master-detail shell. Renders the master `list` on the left and the
 * routed detail pane on the right via <Outlet/>. The right pane's content is
 * driven entirely by the nested route (`:id` panel or index placeholder), so the
 * selection is reflected in the URL.
 */
export default function MasterDetail({ list }: Props) {
  return (
    <div className="master-detail">
      <div className="md-list">{list}</div>
      <div className="md-detail">
        <Outlet />
      </div>
    </div>
  );
}
