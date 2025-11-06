"""
Content extraction and formatting for ZIM entries with MarkItDown integration

Author: mobilemutex
Enhanced with MIME-aware processing and markdown conversion
"""

import logging
import time
import base64
import json
from typing import Optional
from dataclasses import dataclass
from io import BytesIO

import libzim.reader  # pyright: ignore[reportMissingModuleSource]
from markitdown import MarkItDown

from zim_mcp.config import ZimServerConfig
from zim_mcp.zim_manager import ZimManager


@dataclass
class ExtractedContentInfo:
    """Extracted content from a ZIM entry with processing metadata"""

    path: str
    title: str
    content: str
    content_type: str
    content_length: int
    mime_type: str
    processing_time_ms: float
    is_redirect: bool = False


class ContentExtractor:
    """Extract and format content from ZIM entries with MIME-aware processing"""

    def __init__(self, config: ZimServerConfig, zim_manager: ZimManager):
        self.config = config
        self.zim_manager = zim_manager
        self.logger = logging.getLogger("mcp_zim_server.content_extractor")

        # Initialize MarkItDown for HTML→Markdown conversion
        # enable_plugins=False since we only need HTML support
        self.markitdown = MarkItDown(enable_plugins=False)

    def extract_entry_content(
        self, zim_file: str, entry_path: str, raw_output: bool = False
    ) -> Optional[ExtractedContentInfo]:
        """
        Extract and process entry content based on MIME type.

        Args:
            zim_file: Name of the ZIM file
            entry_path: Path to the entry
            raw_output: If True, skip processing and return original content

        Returns:
            ExtractedContentInfo with processed content and timing, or None if not found
        """
        try:
            entry = self.zim_manager.get_entry_by_path(zim_file, entry_path)
            if entry is None:
                return None

            return self._extract_from_entry(entry, raw_output)

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error(
                "Error extracting content from %s in %s: %s", entry_path, zim_file, e
            )
            return None

    def _extract_from_entry(
        self, entry: libzim.reader.Entry, raw_output: bool
    ) -> ExtractedContentInfo:
        """
        Extract content from a ZIM entry with MIME-aware processing and timing.

        Handles redirects, detects MIME type, and applies appropriate processing.
        """

        # Handle redirects immediately
        if entry.is_redirect:
            return ExtractedContentInfo(
                path=entry.path,
                title=entry.title,
                content="[This is a redirect entry]",
                content_type="redirect",
                content_length=0,
                mime_type="redirect",
                processing_time_ms=0.0,
                is_redirect=True,
            )

        # Get item and extract metadata
        item = entry.get_item()
        content_bytes = bytes(item.content)
        mime_type = item.mimetype or "application/octet-stream"

        # Process based on raw_output flag
        if raw_output:
            content, processing_time_ms = self._handle_raw_output(
                content_bytes, mime_type
            )
            format_type = "raw"
        else:
            content, processing_time_ms = self._process_by_mimetype(
                content_bytes, mime_type, entry.path, entry.title
            )
            format_type = self._get_format_type(mime_type)

        # Truncate if too long (after processing)
        if len(content) > self.config.max_content_length:
            content = (
                content[: self.config.max_content_length]
                + "\n\n... [Content truncated at configured limit] ..."
            )

        return ExtractedContentInfo(
            path=entry.path,
            title=entry.title,
            content=content,
            content_type=format_type,
            content_length=len(content_bytes),
            mime_type=mime_type,
            processing_time_ms=processing_time_ms,
            is_redirect=False,
        )

    def _process_by_mimetype(
        self, content_bytes: bytes, mime_type: str, path: str, title: str
    ) -> tuple[str, float]:
        """
        Process content based on MIME type with timing information.

        Returns:
            tuple[str, float]: (processed_content, processing_time_ms)
        """
        start_time = time.time()

        try:
            if mime_type.startswith("text/html"):
                # Convert HTML to Markdown with MarkItDown
                content = self._convert_html_to_markdown(content_bytes)
                elapsed_ms = (time.time() - start_time) * 1000

                # Add metadata footer with timing
                content = self._add_metadata_footer(
                    content, mime_type, len(content_bytes), elapsed_ms
                )
                return content, elapsed_ms

            elif mime_type.startswith("text/"):
                # Plain text, CSS, JavaScript - return as-is
                content = content_bytes.decode("utf-8", errors="replace")
                elapsed_ms = (time.time() - start_time) * 1000
                return content, elapsed_ms

            elif mime_type.startswith("image/"):
                # Images - return metadata description
                # Note: server.py will handle ImageContent for actual image display
                elapsed_ms = (time.time() - start_time) * 1000
                content = self._handle_image_metadata(
                    content_bytes, mime_type, path, title
                )
                return content, elapsed_ms

            elif mime_type.startswith("application/json"):
                # JSON - pretty-print for readability
                raw = content_bytes.decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw)
                    content = json.dumps(parsed, indent=2)
                except json.JSONDecodeError:
                    content = raw
                elapsed_ms = (time.time() - start_time) * 1000
                return content, elapsed_ms

            else:
                # Unknown/binary type - return metadata
                elapsed_ms = (time.time() - start_time) * 1000
                content = self._handle_binary_metadata(content_bytes, mime_type)
                return content, elapsed_ms

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.error("Content processing failed for %s: %s", mime_type, e)
            return f"[Content processing failed: {str(e)}]", elapsed_ms

    def _convert_html_to_markdown(self, content_bytes: bytes) -> str:
        """
        Convert HTML content to clean Markdown using MarkItDown.

        Falls back to raw HTML if conversion fails.
        """
        try:
            content_stream = BytesIO(content_bytes)
            result = self.markitdown.convert_stream(
                content_stream, file_extension=".html"
            )
            return result.text_content

        except Exception as e:
            self.logger.warning(
                "MarkItDown conversion failed: %s. Falling back to raw HTML", e
            )
            # Fallback to basic decode with warning
            raw_html = content_bytes.decode("utf-8", errors="replace")
            return f"[MarkItDown conversion failed: {str(e)}]\n\n{raw_html}"

    def _handle_raw_output(
        self, content_bytes: bytes, mime_type: str
    ) -> tuple[str, float]:
        """
        Handle raw output request - return original content without processing.

        For text: returns UTF-8 decoded string
        For binary: returns base64-encoded string
        """

        if mime_type.startswith("text/"):
            # Text types - return as UTF-8 string
            content = content_bytes.decode("utf-8", errors="replace")
        else:
            # Binary types - return base64 encoded
            b64_content = base64.b64encode(content_bytes).decode("ascii")
            content = f"[Base64 Encoded - {mime_type}]\n\n{b64_content}"

        return content, 0.0  # No processing time for raw output

    def _add_metadata_footer(
        self, content: str, mime_type: str, original_size: int, processing_ms: float
    ) -> str:
        """
        Add metadata footer to content with timing information.

        Appends markdown-formatted metadata section at the end of content.
        """

        size_kb = original_size / 1024

        footer = f"""

---

**Entry Metadata**
- **Original Format**: {mime_type}
- **Converted To**: Markdown
- **Original Size**: {size_kb:.1f} KB
- **Processing Time**: {processing_ms:.1f} ms
"""
        return content + footer

    def _handle_image_metadata(
        self, content_bytes: bytes, mime_type: str, path: str, title: str
    ) -> str:
        """
        Generate metadata description for image content.

        Note: This is only used when extracting through ContentExtractor.
        server.py will return ImageContent directly for actual image display.
        """
        size_kb = len(content_bytes) / 1024

        return f"""# Image Entry

**Title**: {title}
**Path**: {path}
**MIME Type**: {mime_type}
**Size**: {size_kb:.1f} KB ({len(content_bytes):,} bytes)

This is an image file. When accessed through the read_zim_entry tool,
it will be returned as ImageContent for display in your interface.

**Note**: Use `raw_output=True` to get base64-encoded image data if needed.
"""

    def _handle_binary_metadata(self, content_bytes: bytes, mime_type: str) -> str:
        """Generate metadata description for unknown binary content"""

        size_kb = len(content_bytes) / 1024

        return f"""# Binary Content

**MIME Type**: {mime_type}
**Size**: {size_kb:.1f} KB ({len(content_bytes):,} bytes)

This is binary content that cannot be displayed as text.

**Options**:
- Use `raw_output=True` to get base64-encoded data
- This content type may not be suitable for text-based analysis
"""

    def _get_format_type(self, mime_type: str) -> str:
        """Determine format type string from MIME type"""

        if mime_type.startswith("text/html"):
            return "markdown"
        elif mime_type.startswith("text/"):
            return "text"
        elif mime_type.startswith("image/"):
            return "image_metadata"
        elif mime_type.startswith("application/json"):
            return "json"
        else:
            return "binary_metadata"
