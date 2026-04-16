"""Tests for qulab.trace.watcher."""

import json
import time

from qulab.trace.client import TraceClient
from qulab.trace.watcher import NotebookWatcher


def _write_notebook(path, cells):
    """Helper to write a minimal .ipynb file."""
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": cells,
    }
    path.write_text(json.dumps(nb), encoding="utf-8")


class TestNotebookWatcher:
    def test_snapshot_captures_cells(self, tmp_path):
        nb_path = tmp_path / "test.ipynb"
        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 1"]},
            {"id": "c2", "cell_type": "markdown", "source": ["# Title"]},
        ])

        snapshot, order = NotebookWatcher._snapshot(nb_path)
        assert set(order) == {"c1", "c2"}
        assert "c1" in snapshot
        assert "c2" in snapshot

    def test_diff_detects_added(self, tmp_path):
        nb_path = tmp_path / "test.ipynb"
        old_snap = {"c1": "hash1"}
        old_order = ["c1"]
        new_snap = {"c1": "hash1", "c2": "hash2"}
        new_order = ["c1", "c2"]

        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 1"]},
            {"id": "c2", "cell_type": "markdown", "source": ["new"]},
        ])

        changes = NotebookWatcher._diff_snapshots(
            old_snap, old_order, new_snap, new_order, nb_path
        )
        assert len(changes) == 1
        assert changes[0]["id"] == "c2"
        assert changes[0]["change"] == "added"

    def test_diff_detects_removed(self, tmp_path):
        nb_path = tmp_path / "test.ipynb"
        old_snap = {"c1": "hash1", "c2": "hash2"}
        old_order = ["c1", "c2"]
        new_snap = {"c1": "hash1"}
        new_order = ["c1"]

        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 1"]},
        ])

        changes = NotebookWatcher._diff_snapshots(
            old_snap, old_order, new_snap, new_order, nb_path
        )
        assert len(changes) == 1
        assert changes[0]["id"] == "c2"
        assert changes[0]["change"] == "removed"

    def test_diff_detects_modified(self, tmp_path):
        nb_path = tmp_path / "test.ipynb"
        old_snap = {"c1": "hash_old"}
        old_order = ["c1"]
        new_snap = {"c1": "hash_new"}
        new_order = ["c1"]

        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 2"]},
        ])

        changes = NotebookWatcher._diff_snapshots(
            old_snap, old_order, new_snap, new_order, nb_path
        )
        assert len(changes) == 1
        assert changes[0]["change"] == "modified"

    def test_read_cell_summary(self, tmp_path):
        nb_path = tmp_path / "test.ipynb"
        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 1"]},
            {"id": "c2", "cell_type": "markdown", "source": ["# Hello"]},
        ])

        cells = NotebookWatcher._read_cell_summary(nb_path)
        assert len(cells) == 2
        assert cells[0]["id"] == "c1"
        assert cells[0]["cell_type"] == "code"
        assert cells[0]["source"] == "x = 1"
        assert cells[0]["source_hash"]  # non-empty
        assert cells[1]["cell_type"] == "markdown"

    def test_watcher_emits_on_save(self, tmp_path, tmp_buffer_dir):
        nb_path = tmp_path / "test.ipynb"
        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 1"]},
        ])

        client = TraceClient(buffer_dir=tmp_buffer_dir, local_only=True)
        client.start()

        watcher = NotebookWatcher(client, str(nb_path))
        # Ensure initial snapshot was taken
        assert "c1" in watcher._last_snapshot
        watcher.start()

        # Wait for watchdog to settle
        time.sleep(1)

        # Modify the notebook (simulate save)
        _write_notebook(nb_path, [
            {"id": "c1", "cell_type": "code", "source": ["x = 2"]},
            {"id": "c2", "cell_type": "markdown", "source": ["# New"]},
        ])

        # Wait for watchdog to detect the change
        time.sleep(2)

        watcher.stop()
        client.stop()

        # Check that a notebook_save event was emitted
        jsonl_files = list(tmp_buffer_dir.glob("*.jsonl"))
        assert jsonl_files, "No buffer file created"
        lines = jsonl_files[0].read_text("utf-8").strip().split("\n")
        events = [json.loads(line) for line in lines if line.strip()]
        nb_save_events = [
            e for e in events if e["event_type"] == "notebook_save"
        ]
        assert nb_save_events, (
            f"No notebook_save events found. "
            f"Got types: {[e['event_type'] for e in events]}"
        )

        # Watchdog may fire duplicate events; find the one with actual changes.
        # At least one event should have cell_count == 2 (the new state).
        has_two_cells = [
            e for e in nb_save_events if e["payload"]["cell_count"] == 2
        ]
        assert has_two_cells, "No notebook_save event with 2 cells found"

        # Collect all changed_cells across all notebook_save events,
        # because duplicate inotify/FSEvents may cause the second event
        # to see an already-updated snapshot (empty diff).
        all_changes = set()
        for ev in nb_save_events:
            for c in ev["payload"]["changed_cells"]:
                all_changes.add(c["change"])
        assert "added" in all_changes or "modified" in all_changes
