"""Query tool for searching storage."""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage


class QueryTool(BaseTool):
    """Query storage for datasets and documents."""

    name = "query_storage"
    description = "Query storage for datasets and documents"

    parameters = {
        "type": {
            "type": "string",
            "enum": ["dataset", "document"],
            "description": "Type of data to query",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Name pattern (supports * wildcard)",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by tags",
        },
        "state": {
            "type": "string",
            "enum": ["ok", "error", "warning", "unknown"],
            "description": "Filter by state (documents only)",
        },
        "after": {
            "type": "string",
            "description": "Created after this time (ISO format)",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10,
        },
    }

    def __init__(self, storage: "Storage"):
        """Initialize query tool.

        Args:
            storage: Storage instance
        """
        self.storage = storage

    async def execute(
        self,
        type: str,
        name: str | None = None,
        tags: list[str] | None = None,
        state: str | None = None,
        after: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        """Execute query.

        Args:
            type: Type of data ("dataset" or "document")
            name: Name pattern filter
            tags: Tags filter
            state: State filter (documents only)
            after: Created after this time
            limit: Maximum results

        Returns:
            Query results
        """
        try:
            # Parse after timestamp
            after_dt = None
            if after:
                try:
                    after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
                except ValueError:
                    return ToolResult(error=f"Invalid after timestamp: {after}")

            if type == "dataset":
                results = list(
                    self.storage.query_datasets(
                        name=name,
                        tags=tags,
                        after=after_dt,
                        limit=limit,
                    )
                )

                # Serialize results
                data = []
                for ref in results:
                    try:
                        ds = ref.get()
                        data.append({
                            "id": ref.id,
                            "name": ref.name,
                            "tags": ds.tags,
                            "description": ds.description,
                            "created_at": ds.created_at.isoformat() if ds.created_at else None,
                        })
                    except Exception:
                        # Skip datasets that can't be loaded
                        pass

                return ToolResult(
                    data={"datasets": data, "count": len(data)},
                    metadata={"query_type": "dataset"},
                )

            elif type == "document":
                results = list(
                    self.storage.query_documents(
                        name=name,
                        tags=tags,
                        state=state,
                        after=after_dt,
                        limit=limit,
                    )
                )

                # Serialize results
                data = []
                for ref in results:
                    try:
                        doc = ref.get()
                        data.append({
                            "id": ref.id,
                            "name": ref.name,
                            "state": doc.state,
                            "tags": doc.tags,
                            "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        })
                    except Exception:
                        # Skip documents that can't be loaded
                        pass

                return ToolResult(
                    data={"documents": data, "count": len(data)},
                    metadata={"query_type": "document"},
                )

            else:
                return ToolResult(error=f"Unknown query type: {type}")

        except Exception as e:
            return ToolResult(error=f"Query failed: {str(e)}")
