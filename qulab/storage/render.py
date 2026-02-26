"""Content renderer for Markdown with attachment support."""

import base64
import re
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .attachment import Attachment
    from .dataset import Dataset
    from .document import Document
    from .local import LocalStorage


class ContentRenderer:
    """Renderer for content with attachment references.

    Supports rendering Markdown content with attachment:// protocol references.
    """

    # Pattern to match attachment://{id} URLs
    ATTACHMENT_PATTERN = re.compile(r'attachment://(\d+)')

    def __init__(self, storage: "LocalStorage", base_url: str = ""):
        """Initialize renderer.

        Args:
            storage: LocalStorage instance for loading attachments
            base_url: Base URL for generating attachment links
        """
        self.storage = storage
        self.base_url = base_url

    def render_markdown(
        self,
        content: str,
        context: Optional[Union["Dataset", "Document"]] = None
    ) -> str:
        """Render markdown content, replacing attachment:// URLs.

        Args:
            content: Markdown text with attachment:// references
            context: Optional Dataset/Document for resolving relative attachments

        Returns:
            Rendered markdown with resolved attachment URLs
        """
        def replace_attachment(match: re.Match) -> str:
            attachment_id = int(match.group(1))
            try:
                url = self.get_attachment_url(attachment_id, format="data")
                return url
            except (KeyError, RuntimeError):
                # Attachment not found, return original
                return match.group(0)

        return self.ATTACHMENT_PATTERN.sub(replace_attachment, content)

    def render_html(
        self,
        content: str,
        context: Optional[Union["Dataset", "Document"]] = None
    ) -> str:
        """Render content to HTML with attachment embedding.

        Args:
            content: Markdown text with attachment:// references
            context: Optional Dataset/Document for resolving relative attachments

        Returns:
            HTML string with embedded attachments
        """
        try:
            import markdown
            # Convert markdown to HTML
            html = markdown.markdown(
                content,
                extensions=['tables', 'fenced_code', 'toc']
            )
        except ImportError:
            # Fallback: simple paragraph wrapping with markdown image support
            html = f"<p>{content.replace(chr(10), '<br>')}</p>"
            # Handle markdown image syntax: ![alt](attachment://id)
            html = re.sub(
                r'!\[([^\]]*)\]\(attachment://(\d+)\)',
                lambda m: f'<img src="attachment://{m.group(2)}" alt="{m.group(1)}">',
                html
            )
            # Handle markdown link syntax: [text](attachment://id)
            html = re.sub(
                r'(?<!!)\[([^\]]+)\]\(attachment://(\d+)\)',
                lambda m: f'<a href="attachment://{m.group(2)}">{m.group(1)}</a>',
                html
            )

        # Process attachment URLs in HTML
        def replace_image(match: re.Match) -> str:
            """Replace attachment:// in image src."""
            prefix = match.group(1)
            attachment_id = int(match.group(2))
            suffix = match.group(3)

            try:
                att = self.storage.get_attachment(attachment_id)
                if att.mime_type.startswith("image/"):
                    url = self.get_attachment_url(attachment_id, format="data")
                    return f'{prefix}{url}{suffix}'
                else:
                    # Not an image, return link
                    return f'{prefix}#attachment-{attachment_id}{suffix}'
            except (KeyError, RuntimeError):
                return match.group(0)

        def replace_link(match: re.Match) -> str:
            """Replace attachment:// in link href."""
            prefix = match.group(1)
            attachment_id = int(match.group(2))
            suffix = match.group(3)

            try:
                url = self.get_attachment_url(attachment_id, format="data")
                return f'{prefix}{url}{suffix}'
            except (KeyError, RuntimeError):
                return match.group(0)

        # Replace in image src attributes
        html = re.sub(
            r'(<img[^>]*src=["\'])attachment://(\d+)(["\'][^>]*>)',
            replace_image,
            html
        )

        # Replace in link href attributes
        html = re.sub(
            r'(<a[^>]*href=["\'])attachment://(\d+)(["\'][^>]*>)',
            replace_link,
            html
        )

        return html

    def get_attachment_url(
        self,
        attachment_id: int,
        format: str = "data"
    ) -> str:
        """Get URL for an attachment.

        Args:
            attachment_id: Attachment ID
            format: URL format - "data" (base64 data URL), "path" (filesystem path),
                   or "link" (HTTP link if base_url configured)

        Returns:
            URL string suitable for embedding

        Raises:
            KeyError: If attachment not found
            RuntimeError: If storage not available
        """
        from .attachment import Attachment

        attachment = Attachment.load(self.storage, attachment_id)

        if format == "data":
            # Return base64 data URL
            data = attachment.read()
            b64_data = base64.b64encode(data).decode('ascii')
            return f"data:{attachment.mime_type};base64,{b64_data}"

        elif format == "path":
            # Return filesystem path (only works locally)
            # Note: attachments are stored in chunks, return the chunk path
            from pathlib import Path
            hash_prefix = attachment._chunk_hash[:2]
            hash_suffix = attachment._chunk_hash[2:4]
            chunk_path = (
                self.storage.base_path / "chunks" /
                hash_prefix / hash_suffix / attachment._chunk_hash
            )
            return str(chunk_path)

        elif format == "link":
            # Return HTTP link if base_url configured
            if not self.base_url:
                raise RuntimeError("base_url not configured for link format")
            return f"{self.base_url}/attachments/{attachment_id}"

        else:
            raise ValueError(f"Unknown format: {format}")

    def extract_attachments(self, content: str) -> list[int]:
        """Extract all attachment IDs referenced in content.

        Args:
            content: Text containing attachment:// references

        Returns:
            List of attachment IDs
        """
        return [
            int(match.group(1))
            for match in self.ATTACHMENT_PATTERN.finditer(content)
        ]

    def get_attachment_info(self, attachment_id: int) -> dict:
        """Get information about an attachment.

        Args:
            attachment_id: Attachment ID

        Returns:
            Dictionary with attachment metadata

        Raises:
            KeyError: If attachment not found
        """
        from .attachment import Attachment

        attachment = Attachment.load(self.storage, attachment_id)
        return {
            "id": attachment.id,
            "name": attachment.name,
            "mime_type": attachment.mime_type,
            "size": attachment.size,
            "ctime": attachment.ctime.isoformat() if attachment.ctime else None,
            "meta": attachment.meta,
        }

    def render_attachment_list(
        self,
        attachments: list[int],
        format: str = "html"
    ) -> str:
        """Render a list of attachments.

        Args:
            attachments: List of attachment IDs
            format: Output format - "html" or "markdown"

        Returns:
            Rendered attachment list
        """
        if format == "html":
            items = []
            for att_id in attachments:
                try:
                    info = self.get_attachment_info(att_id)
                    url = self.get_attachment_url(att_id, format="data")
                    if info["mime_type"].startswith("image/"):
                        items.append(
                            f'<div class="attachment image">'
                            f'<img src="{url}" alt="{info["name"]}" '
                            f'style="max-width: 100%;"/>'
                            f'<p class="caption">{info["name"]}</p>'
                            f'</div>'
                        )
                    else:
                        items.append(
                            f'<div class="attachment file">'
                            f'<a href="{url}" download="{info["name"]}">'
                            f'{info["name"]} ({info["size"]} bytes)'
                            f'</a></div>'
                        )
                except (KeyError, RuntimeError):
                    items.append(
                        f'<div class="attachment error">'
                        f'Attachment {att_id} not found</div>'
                    )
            return '\n'.join(items)

        elif format == "markdown":
            items = []
            for att_id in attachments:
                try:
                    info = self.get_attachment_info(att_id)
                    if info["mime_type"].startswith("image/"):
                        items.append(f"![{info['name']}](attachment://{att_id})")
                    else:
                        items.append(f"[{info['name']}](attachment://{att_id})")
                except (KeyError, RuntimeError):
                    items.append(f"*[Attachment {att_id} not found]*")
            return '\n'.join(items)

        else:
            raise ValueError(f"Unknown format: {format}")
