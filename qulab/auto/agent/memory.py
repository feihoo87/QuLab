"""Session memory management for persistence."""

import json
from datetime import datetime
from pathlib import Path


class SessionMemory:
    """Session memory for persisting agent conversations."""

    def __init__(self, storage_path: Path | str):
        """Initialize session memory.

        Args:
            storage_path: Base path for storage
        """
        self.path = Path(storage_path) / "sessions"
        self.path.mkdir(parents=True, exist_ok=True)
        self.current_session: str | None = None

    def create_session(self, name: str | None = None) -> str:
        """Create a new session.

        Args:
            name: Optional session name

        Returns:
            Session ID
        """
        if name:
            session_id = name
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}"

        self.current_session = session_id

        # Create session file with header
        session_file = self.path / f"{session_id}.jsonl"
        header = {
            "timestamp": datetime.now().isoformat(),
            "type": "session_start",
            "session_id": session_id,
        }
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(header, ensure_ascii=False) + "\n")

        return session_id

    def load_session(self, session_id: str) -> bool:
        """Load an existing session.

        Args:
            session_id: Session ID to load

        Returns:
            True if session exists
        """
        session_file = self.path / f"{session_id}.jsonl"
        if session_file.exists():
            self.current_session = session_id
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """List all sessions.

        Returns:
            List of session info dicts
        """
        sessions = []
        for session_file in self.path.glob("*.jsonl"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    record = json.loads(first_line)
                    if record.get("type") == "session_start":
                        sessions.append({
                            "session_id": record.get("session_id", session_file.stem),
                            "created_at": record.get("timestamp"),
                        })
            except (json.JSONDecodeError, IOError):
                continue

        return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)

    def load_messages(self) -> list[dict]:
        """Load messages from current session.

        Returns:
            List of message dicts for LLM
        """
        if not self.current_session:
            return []

        session_file = self.path / f"{self.current_session}.jsonl"
        if not session_file.exists():
            return []

        messages = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("type") == "message":
                        data = record.get("data", {})
                        msg = {
                            "role": data.get("role"),
                            "content": data.get("content"),
                        }
                        # Add tool_calls if present
                        if "tool_calls" in data:
                            msg["tool_calls"] = data["tool_calls"]
                        # Add tool_call_id if present
                        if "tool_call_id" in data:
                            msg["tool_call_id"] = data["tool_call_id"]
                        messages.append(msg)
                except json.JSONDecodeError:
                    continue

        return messages

    def append_message(self, role: str, content: str, **metadata) -> None:
        """Append a message to the current session.

        Args:
            role: Message role (user, assistant, tool)
            content: Message content
            **metadata: Additional metadata
        """
        if not self.current_session:
            self.create_session()

        session_file = self.path / f"{self.current_session}.jsonl"

        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "message",
            "data": {
                "role": role,
                "content": content,
                **metadata,
            },
        }

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_decision(self, decision_type: str, details: dict) -> None:
        """Log a decision.

        Args:
            decision_type: Type of decision
            details: Decision details
        """
        if not self.current_session:
            return

        session_file = self.path / f"{self.current_session}.jsonl"

        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "decision",
            "decision_type": decision_type,
            "details": details,
        }

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_tool_execution(self, tool_name: str, arguments: dict, result: dict) -> None:
        """Log a tool execution.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            result: Execution result
        """
        if not self.current_session:
            return

        session_file = self.path / f"{self.current_session}.jsonl"

        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool_execution",
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        }

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_session_history(self) -> list[dict]:
        """Get full session history including decisions and tool executions.

        Returns:
            List of all records
        """
        if not self.current_session:
            return []

        session_file = self.path / f"{self.current_session}.jsonl"
        if not session_file.exists():
            return []

        records = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError:
                    continue

        return records
