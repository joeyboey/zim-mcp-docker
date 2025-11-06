"""
Content extraction and formatting for ZIM entries

Author: mobilemutex

TODO: Integrate markitdown library for clean HTML to Markdown conversion
      https://github.com/microsoft/markitdown
"""

import logging
from typing import Optional
from dataclasses import dataclass
import libzim.reader  # pyright: ignore[reportMissingModuleSource]
from zim_mcp.config import ZimServerConfig
from zim_mcp.zim_manager import ZimManager


@dataclass
class ExtractedContentInfo:
    """Extracted content from a ZIM entry"""

    path: str
    title: str
    content: str
    content_type: str
    content_length: int
    is_redirect: bool = False


class ContentExtractor:
    """Extract and format content from ZIM entries"""

    def __init__(self, config: ZimServerConfig, zim_manager: ZimManager):
        self.config = config
        self.zim_manager = zim_manager
        self.logger = logging.getLogger("mcp_zim_server.content_extractor")

    def extract_entry_content(
        self, zim_file: str, entry_path: str
    ) -> Optional[ExtractedContentInfo]:
        """
        Extract content from a ZIM entry.

        TODO: Implement markitdown conversion for clean markdown output
        Currently returns raw HTML content.

        Args:
            zim_file: Name of the ZIM file
            entry_path: Path to the entry

        Returns:
            ExtractedContentInfo with content, or None if not found
        """
        try:
            entry = self.zim_manager.get_entry_by_path(zim_file, entry_path)
            if entry is None:
                return None

            return self._extract_from_entry(entry)

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error(
                "Error extracting content from %s in %s: %s", entry_path, zim_file, e
            )
            return None

    def _extract_from_entry(self, entry: libzim.reader.Entry) -> ExtractedContentInfo:
        """
        Extract content from a ZIM entry object.

        TODO: Replace basic decoding with markitdown conversion
        """
        try:
            # Get the item
            item = entry.get_item()
            content_bytes = bytes(item.content)

            # Handle redirects
            if entry.is_redirect:
                return ExtractedContentInfo(
                    path=entry.path,
                    title=entry.title,
                    content="[This is a redirect]",
                    content_type="redirect",
                    content_length=0,
                    is_redirect=True,
                )

            # Decode content - basic implementation
            # TODO: Use markitdown here for proper HTML to Markdown conversion
            content = self._decode_content(content_bytes)

            # Truncate if too long
            if len(content) > self.config.max_content_length:
                content = (
                    content[: self.config.max_content_length]
                    + "\n\n... [Content truncated at configured limit] ..."
                )

            return ExtractedContentInfo(
                path=entry.path,
                title=entry.title,
                content=content,
                content_type="html",  # TODO: Change to "markdown" when markitdown integrated
                content_length=len(content_bytes),
                is_redirect=False,
            )

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error("Error extracting from entry %s: %s", entry.path, e)
            raise

    def _decode_content(self, content_bytes: bytes) -> str:
        """
        Decode content bytes to string.

        TODO: Replace with markitdown conversion instead of basic decode
        """
        try:
            # Try UTF-8 first
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # Try Latin-1 as fallback
                return content_bytes.decode("latin-1")
            except UnicodeDecodeError:
                # Last resort: replace errors
                return content_bytes.decode("utf-8", errors="replace")
