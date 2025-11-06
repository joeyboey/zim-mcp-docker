from typing import Annotated, Union
import os

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError, ResourceError
from fastmcp.utilities.types import Image
from mcp.types import ImageContent
from pydantic import Field
from starlette.responses import PlainTextResponse

# Import from package
from zim_mcp import (
    load_config,
    ZimManager,
    SearchEngine,
    ContentExtractor,
    setup_logging,
    ZimFileInfo,
    ZimMetadata,
    CacheInfo,
    ZimFileMetadataResponse,
    ZimEntryContent,
    ZimEntryResponse,
    SearchResult,
    SearchPagination,
    SearchResponse,
    RandomEntry,
    RandomEntriesResponse,
    ListZimFilesResponse,
)

# Load configuration
config = load_config()

# Set up logging
logger = setup_logging(config.log_level)

# Initialize ZIM manager
zim_manager = ZimManager(config)

# Initialize search engine
search_engine = SearchEngine(config, zim_manager)

# Initialize content extractor
content_extractor = ContentExtractor(config, zim_manager)

# Discover ZIM files on startup
logger.info("ZIM files directory: %s", config.zim_files_directory)
discovered_files = zim_manager.discover_zim_files()
logger.info("Found %d ZIM files", len(discovered_files))

# Create MCP server with comprehensive instructions
mcp = FastMCP(
    name="ZIM Offline Knowledge Server",
    instructions="""
🌻 **ZIM MCP Server - Offline Knowledge Access**

🎯 **MISSION**: Provide offline access to Wikipedia and other knowledge
bases through ZIM files with full-text search and content extraction.

📚 **WHAT ARE ZIM FILES?**:
ZIM (Zeno IMproved) files are compressed archives containing entire
Wikipedia dumps and other reference content designed for offline use.
Perfect for research without internet connectivity or accessing large
knowledge bases locally.

🔧 **AVAILABLE TOOLS**:

**list_zim_files** - Discover available offline knowledge bases
• Lists all ZIM files with metadata (title, size, language, article count)
• No parameters required
• Shows which knowledge bases are available for search

**search_zim_files** - Full-text search across millions of articles
• Query with natural language or keywords
• Pagination support for large result sets (use max_results and start_offset)
• Search specific files or all available ZIM files
• Returns ranked results with titles, paths, and content previews

**read_zim_entry** - Extract complete article content
• Intelligent MIME-based processing (HTML→Markdown, images, JSON, text)
• Control output format with raw_output and return_markdown_only parameters
• Content length limiting to prevent token overflow
• Use entry paths from search results
• Best for deep-dive reading after searching

**get_zim_metadata** - Detailed information about ZIM files
• Full metadata including UUID, index types, cache status
• Article and media counts
• Language and creator information

**get_random_entries** - Serendipitous discovery
• Get random articles for exploration
• Great for "tell me something interesting" queries
• Supports multiple ZIM files

**get_main_entry** - Access ZIM homepage/main entry
• Get the designated main entry of a ZIM file (typically the homepage)
• Natural starting point for exploring a ZIM file
• For Wikipedia ZIMs, returns the Wikipedia homepage

💡 **BEST PRACTICES**:

1. **Start with discovery**: Always use list_zim_files() first to see what's available
2. **Smart pagination**: Use small max_results (10-20) to avoid overwhelming responses
3. **Content limits**: Set appropriate maxContentLength to prevent token overflow
4. **Specific searches**: Narrow searches to specific ZIM files when you know the topic
5. **Follow-up pattern**: search → identify relevant entries → read_zim_entry for details

🎯 **TYPICAL WORKFLOWS**:

**Research Workflow** (recommended):
1. list_zim_files() → See available knowledge bases
2. search_zim_files(query="topic", max_results=10) → Find relevant articles
3. read_zim_entry(zim_file="...", entry_path=result.path) → Read full content

**Exploration Workflow**:
1. get_random_entries(count=10) → Discover interesting topics
2. read_zim_entry() → Deep dive on interesting finds

**Focused Research Workflow**:
1. list_zim_files() → Identify the right knowledge base
2. search_zim_files(query="specific topic", zim_files=["specific_file.zim"])
   → Search only relevant file
3. read_zim_entry() → Extract full content

⚠️ **IMPORTANT NOTES**:
• ZIM files can be very large (Wikipedia is 90GB+) - be patient with searches
• Content truncation is automatic to prevent token overflow
• Use pagination (start_offset) for browsing large result sets
• Entry paths from search results can be used directly in read_zim_entry
• Search previews and relevance scores may not be available (limitation of ZIM format)

⚠️ **LIMITATIONS**:
• Search result previews are not available (ZIM format limitation)
• Relevance scores may show as 0.0

🚀 **PERFORMANCE TIPS**:
• Results are cached - repeated searches are faster
• Archives are kept open for performance
• Limit max_results to what you actually need
• Use specific file searches when you know the source
""",
)


@mcp.tool()
async def list_zim_files(
    ctx: Context,
) -> ListZimFilesResponse:
    """
    List all available ZIM files in the configured directory.

    Discovers all ZIM files and returns comprehensive metadata including
    title, description, size, article count, language, and search capabilities.
    Use this as the first step to understand what knowledge bases are available.

    Args:
        ctx: Request context

    Returns:
        ListZimFilesResponse: Contains status, count, and list of ZIM files
        with full metadata (title, size, article count, language, etc.)
    """
    try:
        logger.info("Listing ZIM files")

        # Discover ZIM files
        zim_files = zim_manager.discover_zim_files()

        # Format response
        files_data = []
        for file_info in zim_files:
            files_data.append(
                ZimFileInfo(
                    filename=file_info.filename,
                    title=file_info.title,
                    description=file_info.description,
                    size=file_info.size_formatted,
                    article_count=file_info.article_count,
                    media_count=file_info.media_count,
                    language=file_info.language,
                    creator=file_info.creator,
                    date=file_info.date,
                    has_fulltext_index=file_info.has_fulltext_index,
                    has_title_index=file_info.has_title_index,
                )
            )

        return ListZimFilesResponse(
            status="success", count=len(files_data), files=files_data
        )

    except (RuntimeError, OSError, ValueError) as e:
        logger.error("Error listing ZIM files: %s", e)
        raise ToolError(f"Failed to list ZIM files: {str(e)}") from e


@mcp.tool()
async def get_zim_metadata(
    ctx: Context,
    zim_file: Annotated[
        str,
        Field(
            description="Name or filename of the ZIM file to get metadata for",
            examples=["wikipedia_en_all_2023.zim", "wiktionary_en.zim"],
        ),
    ],
) -> ZimFileMetadataResponse:
    """
    Get detailed metadata about a specific ZIM file.

    Retrieves comprehensive information including title, description, UUID,
    article/media counts, language, creator, and indexing capabilities.
    Useful for understanding the content and capabilities of a ZIM file
    before searching or browsing.

    Args:
        ctx: Request context
        zim_file: Name or filename of the ZIM file

    Returns:
        ZimFileMetadataResponse: Contains status, full metadata, and cache info
    """
    try:
        logger.info("Getting metadata for ZIM file: %s", zim_file)

        # Get file info
        file_info = zim_manager.get_zim_file_info(zim_file)

        if file_info is None:
            raise ToolError(f"ZIM file not found: {zim_file}")

        return ZimFileMetadataResponse(
            status="success",
            metadata=ZimMetadata(
                filename=file_info.filename,
                title=file_info.title,
                description=file_info.description,
                size=file_info.size,
                size_formatted=file_info.size_formatted,
                article_count=file_info.article_count,
                media_count=file_info.media_count,
                language=file_info.language,
                creator=file_info.creator,
                date=file_info.date,
                has_fulltext_index=file_info.has_fulltext_index,
                has_title_index=file_info.has_title_index,
                uuid=file_info.uuid,
            ),
            cache_info=CacheInfo(
                is_cached=file_info.filename in zim_manager.file_info_cache
            ),
        )

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error getting ZIM metadata for %s: %s", zim_file, e)
        raise ToolError(f"Failed to get metadata for '{zim_file}': {str(e)}") from e


@mcp.tool()
async def read_zim_entry(
    ctx: Context,
    zim_file: Annotated[
        str,
        Field(
            description="Name of the ZIM file containing the entry",
            examples=["wikipedia_en_all_2023.zim", "wikinews_en_all_maxi_2025-10.zim"],
        ),
    ],
    entry_path: Annotated[
        str,
        Field(
            description="Path to the entry within the ZIM file (from search results)",
            examples=[
                "Gene",
                "Quantum_mechanics",
                "US_military_confirms_three_deaths_after_B-52_crash_off_Guam",
            ],
        ),
    ],
    raw_output: Annotated[
        bool,
        Field(
            description="If True, returns original content without processing. For text: raw HTML/text. For binary: base64-encoded data",
            examples=[False, True],
        ),
    ] = False,
    return_markdown_only: Annotated[
        bool,
        Field(
            description="If True, returns only markdown text for direct rendering in chat (not wrapped in response object). Only applies to HTML content",
            examples=[False, True],
        ),
    ] = True,
) -> Union[str, ZimEntryResponse, ImageContent]:
    """
    Read and intelligently process entry content from ZIM file.

    Automatically detects content type via MIME type and applies appropriate processing:
    - **HTML** → Clean Markdown (via MarkItDown) with metadata footer including timing
    - **Images** → Returns ImageContent for direct display in agent interface
    - **Plain Text** → Returned as-is without modification
    - **JSON** → Pretty-printed with indentation for readability
    - **Binary** → Metadata description with size information

    Set raw_output=True to bypass all processing and get original content
    (UTF-8 string for text, base64-encoded for binary).

    Set return_markdown_only=True to get markdown as plain text for chat rendering.

    Args:
        ctx: Request context
        zim_file: Name of the ZIM file to read from
        entry_path: Path to entry (from search_zim_files results)
        raw_output: Skip all processing, return original content (default: False)
        return_markdown_only: Return plain markdown string for chat rendering (default: False)

    Returns:
        Union[str, ZimEntryResponse, ImageContent]:
        - str for markdown text when return_markdown_only=True (renders in chat)
        - ZimEntryResponse for structured response with metadata
        - ImageContent for images (displayable in agent interface)
    """
    try:
        logger.info(
            "Reading entry %s from %s (raw_output=%s, markdown_only=%s)",
            entry_path,
            zim_file,
            raw_output,
            return_markdown_only,
        )

        # Get entry
        entry = zim_manager.get_entry_by_path(zim_file, entry_path)
        if entry is None:
            raise ToolError(f"Entry not found: {entry_path} in {zim_file}")

        # Get item and MIME type
        item = entry.get_item()
        content_bytes = bytes(item.content)
        mime_type = item.mimetype or "application/octet-stream"

        # Handle images - return ImageContent for agent display (unless raw_output)
        if not raw_output and mime_type.startswith("image/"):
            return _create_image_content(
                content_bytes, mime_type, entry.path, entry.title
            )

        # For text/HTML content - use ContentExtractor with MIME-aware processing
        extracted = content_extractor.extract_entry_content(
            zim_file, entry_path, raw_output
        )

        if extracted is None:
            raise ToolError(f"Failed to extract content from {entry_path}")

        # Return markdown string only for direct chat rendering
        if (
            return_markdown_only
            and not raw_output
            and extracted.content_type == "markdown"
        ):
            return extracted.content

        # Return structured response with full metadata
        return ZimEntryResponse(
            status="success",
            entry=ZimEntryContent(
                path=extracted.path,
                title=extracted.title,
                content=extracted.content,
                content_length=extracted.content_length,
                format=extracted.content_type,
                mime_type=extracted.mime_type,
                processing_time_ms=extracted.processing_time_ms,
                is_redirect=extracted.is_redirect,
            ),
        )

    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as e:
        logger.error("Error reading entry %s from %s: %s", entry_path, zim_file, e)
        raise ToolError(
            f"Failed to read entry '{entry_path}' from '{zim_file}': {str(e)}"
        ) from e


@mcp.tool()
async def search_zim_files(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            description="Search query - supports natural language or keywords for full-text search",
            examples=[
                "artificial intelligence",
                "quantum physics",
                "Albert Einstein",
                "machine learning",
            ],
            min_length=1,
            max_length=1000,
        ),
    ],
    zim_files: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Optional list of specific ZIM files to search. If not provided, searches all available files",
            examples=[
                ["wikipedia_en_all_2023.zim"],
                ["wiktionary_en.zim", "wikiquote_en.zim"],
            ],
        ),
    ] = None,
    max_results: Annotated[
        int,
        Field(
            description="Maximum number of search results to return (prevents overwhelming responses)",
            ge=1,
            le=100,
            examples=[10, 20, 50],
        ),
    ] = 20,
    start_offset: Annotated[
        int,
        Field(
            description="Pagination offset - starting position for results (0-based index)",
            ge=0,
            examples=[0, 20, 40, 60],
        ),
    ] = 0,
) -> SearchResponse:
    """
    Search for content across one or multiple ZIM files with full-text indexing.

    Performs full-text search across millions of articles, returning ranked
    results with titles, paths, relevance scores, and content previews.
    Results are ranked by relevance and support pagination for large result sets.

    Args:
        ctx: Request context
        query: Search query string (natural language or keywords)
        zim_files: Optional list of specific ZIM files (default: search all)
        max_results: Maximum results to return (1-100, default: 20)
        start_offset: Pagination offset (default: 0)

    Returns:
        SearchResponse: Contains status, query, count, results list, and
        pagination info. Each result includes zim_file, path, title, score,
        preview, and redirect status.
    """
    try:
        logger.info("Searching ZIM files for: %s", query)

        # Validate parameters
        if max_results <= 0 or max_results > config.max_search_results:
            raise ToolError(
                f"Invalid max_results: {max_results}. Must be between 1 and {config.max_search_results}"
            )

        if start_offset < 0:
            raise ToolError(f"Invalid start_offset: {start_offset}. Must be >= 0")

        # Perform search
        if zim_files:
            # Search specific files
            results = search_engine.search_multiple_zim(
                zim_files, query, max_results, start_offset
            )
        else:
            # Search all files
            results = search_engine.search_all_zim_files(
                query, max_results, start_offset
            )

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append(
                SearchResult(
                    zim_file=result.zim_file,
                    path=result.path,
                    title=result.title,
                    score=result.score,
                    preview=result.preview,
                    is_redirect=result.is_redirect,
                )
            )

        return SearchResponse(
            status="success",
            query=query,
            count=len(formatted_results),
            results=formatted_results,
            pagination=SearchPagination(
                start_offset=start_offset,
                max_results=max_results,
                has_more=len(results) == max_results,
            ),
        )

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error searching ZIM files for '%s': %s", query, e)
        raise ToolError(f"Search failed for query '{query}': {str(e)}") from e


@mcp.tool()
async def get_random_entries(
    ctx: Context,
    zim_files: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Optional list of specific ZIM files to get random entries from. If not provided, uses all available files",
            examples=[
                ["wikipedia_en_all_2023.zim"],
                ["wiktionary_en.zim", "wikiquote_en.zim"],
            ],
        ),
    ] = None,
    count: Annotated[
        int,
        Field(
            description="Number of random entries to return for serendipitous discovery",
            ge=1,
            le=50,
            examples=[5, 10, 20],
        ),
    ] = 5,
) -> RandomEntriesResponse:
    """
    Get random entries from ZIM files for serendipitous discovery and exploration.

    Perfect for "tell me something interesting" queries, discovering new topics,
    or getting a feel for what content is available in a ZIM file. Entries are
    distributed across specified files or all available files if none specified.

    Args:
        ctx: Request context
        zim_files: Optional list of specific ZIM files (default: all available)
        count: Number of random entries to return (1-50, default: 5)

    Returns:
        RandomEntriesResponse: Contains status, count, and list of random
        entries with zim_file, path, title, and redirect status
    """
    try:
        logger.info("Getting %d random entries", count)

        # Validate count
        if count <= 0 or count > 50:
            raise ToolError(f"Invalid count: {count}. Must be between 1 and 50")

        # Get available files if none specified
        if zim_files is None:
            available_files = zim_manager.discover_zim_files()
            zim_files = [f.filename for f in available_files]

        if not zim_files:
            raise ToolError("No ZIM files available for random entry selection")

        random_entries = []
        entries_per_file = max(1, count // len(zim_files))

        for zim_file in zim_files:
            try:
                for _ in range(entries_per_file):
                    if len(random_entries) >= count:
                        break

                    entry = zim_manager.get_random_entry(zim_file)
                    if entry:
                        random_entries.append(
                            RandomEntry(
                                zim_file=zim_file,
                                path=entry.path,
                                title=entry.title,
                                is_redirect=entry.is_redirect,
                            )
                        )
            except (FileNotFoundError, RuntimeError, ValueError, OSError) as e:
                logger.warning("Error getting random entry from %s: %s", zim_file, e)
                continue

        return RandomEntriesResponse(
            status="success", count=len(random_entries), entries=random_entries
        )

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error getting random entries: %s", e)
        raise ToolError(f"Failed to get random entries: {str(e)}") from e


@mcp.tool()
async def get_main_entry(
    ctx: Context,
    zim_file: Annotated[
        str,
        Field(
            description="Name of the ZIM file to get the main entry from",
            examples=["wikipedia_en_all_2023.zim", "wiktionary_en.zim"],
        ),
    ],
    raw_output: Annotated[
        bool,
        Field(
            description="If True, returns original content without processing",
            examples=[False, True],
        ),
    ] = False,
    return_markdown_only: Annotated[
        bool,
        Field(
            description="If True, returns only markdown text for direct rendering in chat",
            examples=[False, True],
        ),
    ] = True,
) -> Union[str, ZimEntryResponse, ImageContent]:
    """
    Get the main entry (homepage) of a ZIM file.

    Every ZIM file can have a designated main entry, typically the homepage
    or introduction page. For Wikipedia ZIMs, this is usually the Wikipedia
    homepage. This provides a natural starting point for exploring a ZIM file.

    Args:
        ctx: Request context
        zim_file: Name of the ZIM file
        raw_output: Skip all processing, return original content (default: False)
        return_markdown_only: Return plain markdown string for chat rendering (default: True)

    Returns:
        Union[str, ZimEntryResponse, ImageContent]:
        - str for markdown text when return_markdown_only=True
        - ZimEntryResponse for structured response with metadata
        - ImageContent for images (if main entry is an image)
    """
    try:
        logger.info("Getting main entry from %s", zim_file)

        # Get main entry
        entry = zim_manager.get_main_entry(zim_file)
        if entry is None:
            raise ToolError(f"No main entry found in {zim_file}")

        # Get item and MIME type
        item = entry.get_item()
        content_bytes = bytes(item.content)
        mime_type = item.mimetype or "application/octet-stream"

        # Handle images - return ImageContent for agent display (unless raw_output)
        if not raw_output and mime_type.startswith("image/"):
            return _create_image_content(
                content_bytes, mime_type, entry.path, entry.title
            )

        # For text/HTML content - use ContentExtractor directly with entry object
        # (avoids redundant path lookup that may fail for main entries)
        extracted = content_extractor._extract_from_entry(entry, raw_output, zim_file)

        # Return markdown string only for direct chat rendering
        if (
            return_markdown_only
            and not raw_output
            and extracted.content_type == "markdown"
        ):
            return extracted.content

        # Return structured response with full metadata
        return ZimEntryResponse(
            status="success",
            entry=ZimEntryContent(
                path=extracted.path,
                title=extracted.title,
                content=extracted.content,
                content_length=extracted.content_length,
                format=extracted.content_type,
                mime_type=extracted.mime_type,
                processing_time_ms=extracted.processing_time_ms,
                is_redirect=extracted.is_redirect,
            ),
        )

    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as e:
        logger.error("Error getting main entry from %s: %s", zim_file, e)
        raise ToolError(f"Failed to get main entry from '{zim_file}': {str(e)}") from e


def _create_image_content(
    image_bytes: bytes, mime_type: str, path: str, title: str
) -> ImageContent:
    """
    Create ImageContent for display in agent interface.

    Converts image bytes to FastMCP ImageContent that agents can display directly.

    Args:
        image_bytes: Raw image data
        mime_type: MIME type (e.g., "image/png", "image/jpeg")
        path: Entry path
        title: Entry title

    Returns:
        ImageContent for MCP display
    """
    # Map MIME types to image formats
    format_map = {
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/jpg": "jpeg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        "image/bmp": "bmp",
    }

    image_format = format_map.get(mime_type, "png")  # Default to PNG

    logger.info(
        "Creating ImageContent for %s (%s, %d bytes)",
        title,
        mime_type,
        len(image_bytes),
    )

    # Create Image object and convert to ImageContent
    img_obj = Image(data=image_bytes, format=image_format)
    return img_obj.to_image_content()


# ============================================================================
# MCP Resource Endpoints (Read-Only Data Access)
# ============================================================================


@mcp.resource("zim://files")
async def list_zim_files_resource(ctx: Context) -> dict:
    """
    List all available ZIM files as a resource.

    Resource URI: zim://files

    Provides read-only access to the list of ZIM files with metadata.
    Complements the list_zim_files() tool.
    """
    try:
        files = zim_manager.discover_zim_files()

        return {
            "count": len(files),
            "files": [
                {
                    "filename": f.filename,
                    "title": f.title,
                    "description": f.description,
                    "size": f.size_formatted,
                    "article_count": f.article_count,
                    "media_count": f.media_count,
                    "language": f.language,
                    "creator": f.creator,
                    "date": f.date,
                    "has_fulltext_index": f.has_fulltext_index,
                    "has_title_index": f.has_title_index,
                }
                for f in files
            ],
        }

    except Exception as e:
        logger.error("Resource error (zim://files): %s", e)
        raise ResourceError(f"Failed to list ZIM files: {str(e)}") from e


@mcp.resource("zim://{filename}/metadata")
async def get_zim_metadata_resource(filename: str, ctx: Context) -> dict:
    """
    Get detailed metadata for a specific ZIM file as a resource.

    Resource URI template: zim://{filename}/metadata

    Examples:
    - zim://wikipedia_en_100_2025-10.zim/metadata
    - zim://wikinews_en_all_maxi_2025-10.zim/metadata

    Provides read-only access to ZIM file metadata.
    Complements the get_zim_metadata() tool.
    """
    try:
        file_info = zim_manager.get_zim_file_info(filename)

        if file_info is None:
            raise ResourceError(f"ZIM file not found: {filename}")

        return {
            "filename": file_info.filename,
            "title": file_info.title,
            "description": file_info.description,
            "size": file_info.size,
            "size_formatted": file_info.size_formatted,
            "article_count": file_info.article_count,
            "media_count": file_info.media_count,
            "language": file_info.language,
            "creator": file_info.creator,
            "date": file_info.date,
            "has_fulltext_index": file_info.has_fulltext_index,
            "has_title_index": file_info.has_title_index,
            "uuid": file_info.uuid,
        }

    except Exception as e:
        logger.error("Resource error (zim://%s/metadata): %s", filename, e)
        raise ResourceError(f"Failed to get metadata for '{filename}': {str(e)}") from e


@mcp.resource("zim://{filename}/entry/{path*}")
async def read_zim_entry_resource(filename: str, path: str, ctx: Context) -> str:
    """
    Read entry content as a resource (returns markdown).

    Resource URI template: zim://{filename}/entry/{path*}

    The wildcard {path*} captures the full entry path including any slashes.

    Examples:
    - zim://wikipedia_en_100_2025-10.zim/entry/Gene
    - zim://wikinews_en_all_maxi_2025-10.zim/entry/US_military_confirms_three_deaths_after_B-52_crash_off_Guam

    Returns markdown-converted content (for HTML entries) or plain text.
    For images and binary content, use the read_zim_entry tool instead.

    Provides read-only access to entry content.
    Complements the read_zim_entry() tool.
    """
    try:
        logger.info("Resource request: zim://%s/entry/%s", filename, path)

        extracted = content_extractor.extract_entry_content(
            filename, path, raw_output=False
        )

        if extracted is None:
            raise ResourceError(f"Entry not found: {path} in {filename}")

        # For resources, always return text content
        # Images and binary content return metadata descriptions
        return extracted.content

    except Exception as e:
        logger.error("Resource error (zim://%s/entry/%s): %s", filename, path, e)
        raise ResourceError(
            f"Failed to read entry '{path}' from '{filename}': {str(e)}"
        ) from e


# ============================================================================
# Health Check Endpoint (for Docker/Kubernetes)
# ============================================================================


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request) -> PlainTextResponse:
    """
    Health check endpoint for container orchestration.

    Returns HTTP 200 if server is healthy, 503 if unhealthy.
    Used by Docker healthcheck and Kubernetes liveness probes.
    """
    try:
        # Check if ZIM files are accessible
        files = zim_manager.discover_zim_files()

        return PlainTextResponse(
            f"OK - {len(files)} ZIM files available", status_code=200
        )
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return PlainTextResponse(f"ERROR: {str(e)}", status_code=503)


# ============================================================================
# Server Startup - Multi-Transport Support
# ============================================================================


if __name__ == "__main__":
    # Get transport configuration from environment variables
    transport = os.getenv("FASTMCP_TRANSPORT", "stdio")
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", "8000"))

    logger.info("=" * 60)
    logger.info("ZIM MCP Server - Starting")
    logger.info("=" * 60)
    logger.info(f"Transport: {transport}")
    logger.info(f"ZIM files directory: {config.zim_files_directory}")
    logger.info(f"Found {len(discovered_files)} ZIM files available")
    logger.info("=" * 60)

    if transport == "stdio":
        logger.info("Starting STDIO transport (for local MCP clients)")
        mcp.run(transport="stdio")

    elif transport in ["http", "streamable-http"]:
        logger.info(f"Starting HTTP (Streamable) transport on {host}:{port}")
        logger.info(f"MCP endpoint: http://{host}:{port}/mcp/")
        logger.info(f"Health check: http://{host}:{port}/health")
        mcp.run(transport="http", host=host, port=port)

    elif transport == "sse":
        logger.info(f"Starting SSE transport on {host}:{port}")
        logger.info(f"SSE endpoint: http://{host}:{port}/sse")
        logger.info(f"Health check: http://{host}:{port}/health")
        mcp.run(transport="sse", host=host, port=port)

    else:
        raise ValueError(
            f"Invalid FASTMCP_TRANSPORT: {transport}. "
            f"Valid options: 'stdio', 'http', 'sse'"
        )
