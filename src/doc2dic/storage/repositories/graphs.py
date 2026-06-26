"""Graph snapshot SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.domain import AppGraph, GraphSnapshot
from doc2dic.storage.sqlite_rows import text_cell


class GraphRepository:
    """Persist graph projection snapshots."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def upsert_snapshot(self, snapshot: GraphSnapshot) -> None:
        """Insert or replace a graph snapshot."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into graph_snapshots(id, created_at, graph_json)
                values (?, ?, ?)
                on conflict(id) do update set
                  created_at = excluded.created_at,
                  graph_json = excluded.graph_json
                """,
                (
                    snapshot.id,
                    snapshot.created_at,
                    snapshot.graph.model_dump_json(by_alias=True),
                ),
            )

    def get_snapshot(self, snapshot_id: str) -> GraphSnapshot | None:
        """Return a graph snapshot by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from graph_snapshots where id = ?",
                (snapshot_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return GraphSnapshot(
            id=text_cell(row, "id"),
            createdAt=text_cell(row, "created_at"),
            graph=AppGraph.model_validate_json(text_cell(row, "graph_json")),
        )
