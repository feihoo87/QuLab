"""Lesson management tools for self-learning."""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage


class SaveLessonTool(BaseTool):
    """Save a learned lesson to storage."""

    name = "save_lesson"
    description = """Save a lesson learned from experiment execution to storage.

    Use this tool when:
    - A skill execution failed and you found the solution
    - You discovered optimal parameters for a measurement
    - You identified a common pitfall or mistake
    - You want to document troubleshooting steps

    The lesson will be stored as a Document with tag 'lesson' for future reference."""

    parameters = {
        "title": {
            "type": "string",
            "description": "Short title for the lesson",
            "required": True,
        },
        "problem": {
            "type": "string",
            "description": "Description of the problem or situation",
            "required": True,
        },
        "solution": {
            "type": "string",
            "description": "The solution or key insight",
            "required": True,
        },
        "skill": {
            "type": "string",
            "description": "Related skill name (if applicable)",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Additional tags for categorization",
        },
        "context": {
            "type": "string",
            "description": "Additional context (e.g., instrument config, parameters used)",
        },
    }

    def __init__(self, storage: "Storage"):
        """Initialize save lesson tool.

        Args:
            storage: Storage instance
        """
        self.storage = storage

    async def execute(
        self,
        title: str,
        problem: str,
        solution: str,
        skill: str | None = None,
        tags: list[str] | None = None,
        context: str | None = None,
        **_kwargs
    ) -> ToolResult:
        """Save a lesson.

        Args:
            title: Lesson title
            problem: Problem description
            solution: Solution description
            skill: Related skill name
            tags: Additional tags
            context: Additional context
            **_kwargs: Ignored additional arguments

        Returns:
            ToolResult with saved document info
        """
        try:
            # Build tags
            lesson_tags = ["lesson"]
            if skill:
                lesson_tags.append(f"skill:{skill}")
            if tags:
                lesson_tags.extend(tags)

            # Build content
            content_parts = [
                f"## 问题\n\n{problem}\n",
                f"## 解决方案\n\n{solution}\n",
            ]
            if context:
                content_parts.append(f"## 上下文\n\n{context}\n")
            if skill:
                content_parts.append(f"## 相关 Skill\n\n- {skill}")

            content = "\n".join(content_parts)

            # Create document using storage.create_document
            doc_ref = self.storage.create_document(
                name=f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{title[:30]}",
                data={"content": content},
                state="ok",
                tags=lesson_tags,
                title=title,
                skill=skill,
                created_at=datetime.now().isoformat(),
                lesson_type="experience",
            )

            return ToolResult(
                data={
                    "document_id": doc_ref.id,
                    "title": title,
                    "tags": lesson_tags,
                },
                metadata={"action": "save_lesson", "skill": skill},
            )

        except Exception as e:
            return ToolResult(error=f"Failed to save lesson: {e!s}")


class QueryLessonsTool(BaseTool):
    """Query saved lessons from storage."""

    name = "query_lessons"
    description = """Query previously saved lessons from storage.

    Use this tool to:
    - Find lessons related to a specific skill
    - Look up solutions to previous problems
    - Review troubleshooting steps
    - Learn from past experiments

    Lessons are stored as Documents with tag 'lesson'."""

    parameters = {
        "skill": {
            "type": "string",
            "description": "Filter by related skill name",
        },
        "keyword": {
            "type": "string",
            "description": "Search in title and content",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by additional tags",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10,
        },
    }

    def __init__(self, storage: "Storage"):
        """Initialize query lessons tool.

        Args:
            storage: Storage instance
        """
        self.storage = storage

    async def execute(
        self,
        skill: str | None = None,
        keyword: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        **_kwargs
    ) -> ToolResult:
        """Query lessons.

        Args:
            skill: Filter by skill name
            keyword: Search keyword
            tags: Additional tags filter
            limit: Maximum results
            **_kwargs: Ignored additional arguments

        Returns:
            ToolResult with matching lessons
        """
        try:
            # Build query tags - always include 'lesson' tag
            query_tags = ["lesson"]
            if skill:
                query_tags.append(f"skill:{skill}")
            if tags:
                query_tags.extend(tags)

            # Query documents
            results = list(
                self.storage.query_documents(
                    tags=query_tags,
                    limit=limit * 2,  # Get more to filter by keyword
                )
            )

            # Filter and format results
            lessons = []
            for doc_ref in results:
                try:
                    doc = doc_ref.get()
                    doc_data = doc.data if hasattr(doc, 'data') else {}
                    doc_meta = doc.meta if hasattr(doc, 'meta') else {}

                    # Keyword filter
                    if keyword:
                        keyword_lower = keyword.lower()
                        content = doc_data.get('content', '').lower() if isinstance(doc_data, dict) else ''
                        title = doc_meta.get('title', '').lower() if isinstance(doc_meta, dict) else ''
                        if keyword_lower not in content and keyword_lower not in title:
                            continue

                    doc_tags = [t for t in (doc.tags if hasattr(doc, 'tags') else []) if t != 'lesson']
                    summary = doc_data.get('content', '')[:200] + '...' if isinstance(doc_data, dict) and len(doc_data.get('content', '')) > 200 else ''

                    lessons.append({
                        "id": doc_ref.id,
                        "title": doc_meta.get('title', 'Untitled') if isinstance(doc_meta, dict) else 'Untitled',
                        "skill": doc_meta.get('skill') if isinstance(doc_meta, dict) else None,
                        "tags": doc_tags,
                        "created_at": doc.ctime.isoformat() if hasattr(doc, 'ctime') and doc.ctime else None,
                        "summary": summary,
                    })

                    if len(lessons) >= limit:
                        break

                except Exception:
                    # Skip documents that can't be loaded
                    pass

            return ToolResult(
                data={
                    "lessons": lessons,
                    "count": len(lessons),
                    "filters": {
                        "skill": skill,
                        "keyword": keyword,
                        "tags": tags,
                    },
                },
                metadata={"action": "query_lessons"},
            )

        except Exception as e:
            return ToolResult(error=f"Failed to query lessons: {e!s}")


class CreateGuideTool(BaseTool):
    """Create a comprehensive guide from accumulated lessons."""

    name = "create_guide"
    description = """Create a comprehensive guide document from multiple lessons.

    Use this tool to:
    - Compile lessons into a skill usage guide
    - Create troubleshooting handbooks
    - Document best practices

    The guide will be stored as a Document with tag 'guide'."""

    parameters = {
        "title": {
            "type": "string",
            "description": "Guide title",
            "required": True,
        },
        "skill": {
            "type": "string",
            "description": "Target skill for the guide",
            "required": True,
        },
        "description": {
            "type": "string",
            "description": "Brief description of the guide's purpose",
            "required": True,
        },
        "lesson_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific lesson document IDs to include (optional, if empty uses all for this skill)",
        },
    }

    def __init__(self, storage: "Storage"):
        """Initialize create guide tool.

        Args:
            storage: Storage instance
        """
        self.storage = storage

    async def execute(
        self,
        title: str,
        skill: str,
        description: str,
        lesson_ids: list[str] | None = None,
        **_kwargs
    ) -> ToolResult:
        """Create a guide from lessons.

        Args:
            title: Guide title
            skill: Target skill
            description: Guide description
            lesson_ids: Specific lesson IDs to include
            **_kwargs: Ignored additional arguments

        Returns:
            ToolResult with created guide info
        """
        try:
            # Get lessons
            if lesson_ids:
                lessons = []
                for lid in lesson_ids:
                    try:
                        doc = self.storage.get_document(int(lid))
                        if doc:
                            doc_data = doc.data if hasattr(doc, 'data') else {}
                            doc_meta = doc.meta if hasattr(doc, 'meta') else {}
                            content = doc_data.get('content', '') if isinstance(doc_data, dict) else ''
                            lesson_title = doc_meta.get('title', 'Untitled') if isinstance(doc_meta, dict) else 'Untitled'
                            lessons.append((lesson_title, content))
                    except Exception:
                        pass
            else:
                # Query all lessons for this skill
                results = list(
                    self.storage.query_documents(
                        tags=["lesson", f"skill:{skill}"],
                        limit=50,
                    )
                )
                lessons = []
                for doc_ref in results:
                    try:
                        doc = doc_ref.get()
                        doc_data = doc.data if hasattr(doc, 'data') else {}
                        doc_meta = doc.meta if hasattr(doc, 'meta') else {}
                        content = doc_data.get('content', '') if isinstance(doc_data, dict) else ''
                        lesson_title = doc_meta.get('title', 'Untitled') if isinstance(doc_meta, dict) else 'Untitled'
                        lessons.append((lesson_title, content))
                    except Exception:
                        pass

            if not lessons:
                return ToolResult(
                    error=f"No lessons found for skill '{skill}'"
                )

            # Build guide content
            content_parts = [
                f"# {title}\n",
                f"**Skill**: {skill}\n",
                f"**Description**: {description}\n",
                f"**Created**: {datetime.now().isoformat()}\n",
                f"**Compiled from**: {len(lessons)} lessons\n",
                "---\n",
            ]

            for i, (lesson_title, lesson_content) in enumerate(lessons, 1):
                content_parts.append(f"\n## {i}. {lesson_title}\n")
                content_parts.append(lesson_content)
                content_parts.append("\n")

            content = "\n".join(content_parts)

            # Create guide document
            doc_ref = self.storage.create_document(
                name=f"guide_{skill}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                data={"content": content},
                state="ok",
                tags=["guide", f"skill:{skill}", "compiled"],
                title=title,
                skill=skill,
                description=description,
                lesson_count=len(lessons),
                created_at=datetime.now().isoformat(),
            )

            return ToolResult(
                data={
                    "document_id": doc_ref.id,
                    "title": title,
                    "skill": skill,
                    "lesson_count": len(lessons),
                },
                metadata={"action": "create_guide", "skill": skill},
            )

        except Exception as e:
            return ToolResult(error=f"Failed to create guide: {e!s}")
