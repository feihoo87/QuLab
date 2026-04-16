"""Notebook file watcher for the trace system.

Monitors ``.ipynb`` file saves via ``watchdog`` to capture the full
notebook structure including markdown cells, cell order, and content
changes that are invisible to IPython kernel hooks.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .client import TraceClient
from .models import EventType

logger = logging.getLogger(__name__)


class NotebookWatcher:
    """Watches a notebook file for saves and emits NOTEBOOK_SAVE events.

    Detects which cells changed (added, removed, modified) between saves
    by comparing cell id + source hash snapshots.
    """

    def __init__(
        self,
        client: TraceClient,
        notebook_path: str,
    ):
        self.client = client
        self.notebook_path = notebook_path
        self._abs_path = self._resolve_path(notebook_path)
        self._observer: Any = None
        self._last_snapshot: dict[str, str] = {}  # cell_id -> source_hash
        self._last_cell_order: list[str] = []
        self._running = False

        # Take initial snapshot
        if self._abs_path and self._abs_path.exists():
            self._last_snapshot, self._last_cell_order = self._snapshot(
                self._abs_path
            )

    def start(self) -> None:
        """Start watching the notebook file for changes."""
        if self._abs_path is None:
            logger.debug("No notebook path to watch")
            return

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.debug("watchdog not available, notebook watcher disabled")
            return

        watch_dir = str(self._abs_path.parent)
        filename = self._abs_path.name

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event: Any) -> None:
                if event.is_directory:
                    return
                if Path(event.src_path).name == filename:
                    watcher.on_notebook_modified()

        self._observer = Observer()
        self._observer.schedule(_Handler(), watch_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        self._running = True
        logger.debug("Notebook watcher started for %s", self._abs_path)

    def stop(self) -> None:
        """Stop watching."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._running = False

    def on_notebook_modified(self) -> None:
        """Handle notebook file modification (save)."""
        if self._abs_path is None or not self._abs_path.exists():
            return

        try:
            new_snapshot, new_order = self._snapshot(self._abs_path)
        except Exception:  # pylint: disable=broad-except
            logger.debug("Failed to read notebook file", exc_info=True)
            return

        # Compute changes
        changed_cells = self._diff_snapshots(
            self._last_snapshot, self._last_cell_order,
            new_snapshot, new_order,
            self._abs_path,
        )

        # Build full cell list for the event
        cells = self._read_cell_summary(self._abs_path)

        self.client.emit(
            EventType.NOTEBOOK_SAVE,
            {
                "notebook_path": self.notebook_path,
                "cells": cells,
                "cell_count": len(cells),
                "changed_cells": changed_cells,
            },
        )

        self._last_snapshot = new_snapshot
        self._last_cell_order = new_order

    @staticmethod
    def _snapshot(path: Path) -> tuple[dict[str, str], list[str]]:
        """Read notebook and return (cell_id -> source_hash, cell_id_order)."""
        with open(path, encoding="utf-8") as f:
            nb = json.load(f)

        snapshot: dict[str, str] = {}
        order: list[str] = []
        for cell in nb.get("cells", []):
            cell_id = cell.get("id", "")
            source = "".join(cell.get("source", []))
            h = hashlib.sha256(source.encode("utf-8")).hexdigest()
            snapshot[cell_id] = h
            order.append(cell_id)

        return snapshot, order

    @staticmethod
    def _diff_snapshots(
        old_snap: dict[str, str],
        old_order: list[str],
        new_snap: dict[str, str],
        new_order: list[str],
        path: Path,
    ) -> list[dict]:
        """Compute which cells changed between two snapshots."""
        changes: list[dict] = []

        # Read new notebook for cell types
        cell_types: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as f:
                nb = json.load(f)
            for cell in nb.get("cells", []):
                cell_types[cell.get("id", "")] = cell.get("cell_type", "")
        except Exception:  # pylint: disable=broad-except
            pass

        old_ids = set(old_snap.keys())
        new_ids = set(new_snap.keys())

        # Added cells
        for cid in new_order:
            if cid not in old_ids:
                changes.append({
                    "id": cid,
                    "cell_type": cell_types.get(cid, ""),
                    "change": "added",
                })

        # Removed cells
        for cid in old_order:
            if cid not in new_ids:
                changes.append({
                    "id": cid,
                    "cell_type": "",
                    "change": "removed",
                })

        # Modified cells (same id, different hash)
        for cid in new_order:
            if cid in old_ids and old_snap.get(cid) != new_snap.get(cid):
                changes.append({
                    "id": cid,
                    "cell_type": cell_types.get(cid, ""),
                    "change": "modified",
                })

        return changes

    @staticmethod
    def _read_cell_summary(path: Path) -> list[dict]:
        """Read notebook and return a summary of all cells."""
        try:
            with open(path, encoding="utf-8") as f:
                nb = json.load(f)
        except Exception:  # pylint: disable=broad-except
            return []

        cells = []
        for cell in nb.get("cells", []):
            source = "".join(cell.get("source", []))
            cells.append({
                "id": cell.get("id", ""),
                "cell_type": cell.get("cell_type", ""),
                "source": source,
                "source_hash": hashlib.sha256(
                    source.encode("utf-8")
                ).hexdigest(),
            })
        return cells

    @staticmethod
    def _resolve_path(notebook_path: str) -> Optional[Path]:
        """Resolve notebook path to absolute path."""
        if not notebook_path:
            return None
        p = Path(notebook_path)
        if p.is_absolute() and p.exists():
            return p

        # Try relative to Jupyter server root
        import os

        server_root = os.environ.get("JUPYTER_SERVER_ROOT", "")
        if server_root:
            candidate = Path(server_root) / notebook_path
            if candidate.exists():
                return candidate

        # Try CWD
        candidate = Path.cwd() / notebook_path
        if candidate.exists():
            return candidate

        # Try home
        candidate = Path.home() / notebook_path
        if candidate.exists():
            return candidate

        return p if p.exists() else None
