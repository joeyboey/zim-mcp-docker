from typing import List, Optional, Annotated
import json

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import Field

# Import from package
from zim_mcp import (
    load_config,
    ZimManager,
    SearchEngine,
    ContentExtractor,
    FileDiscovery,
    setup_logging,
    clean_html_content,
    ZimFileInfo,
    ZimMetadata,
    CacheInfo,
    ZimFileMetadataResponse,
    ZimEntryContent,
    ZimEntryResponse,
    SearchResult,
    SearchPagination,
    SearchResponse,
    ExtractedContent,
    SearchAndExtractResponse,
    BrowsedEntry,
    BrowseResponse,
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

# Initialize file discovery
file_discovery = FileDiscovery(config)

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
• Multiple formats: 'text' (clean markdown), 'html' (formatted), 'raw'
• Content length limiting to prevent token overflow
• Use entry paths from search results
• Best for deep-dive reading after searching

**get_zim_metadata** - Detailed information about ZIM files
• Full metadata including UUID, index types, cache status
• Article and media counts
• Language and creator information

**search_and_extract_content** - Combined search + extract in one call
• One-shot operation for quick research
• Returns search results with full content included
• Faster than separate search + read operations
• Ideal for "give me info about X" queries

**browse_zim_entries** - Pattern-based discovery
• Browse by path or title patterns
• Explore file structure and organization
• Useful for discovering related content

**get_random_entries** - Serendipitous discovery
• Get random articles for exploration
• Great for "tell me something interesting" queries
• Supports multiple ZIM files

💡 **BEST PRACTICES**:

1. **Start with discovery**: Always use list_zim_files() first to see what's available
2. **Smart pagination**: Use small max_results (10-20) to avoid overwhelming responses
3. **Content limits**: Set appropriate maxContentLength to prevent token overflow
4. **Specific searches**: Narrow searches to specific ZIM files when you know the topic
5. **Follow-up pattern**: search → identify relevant entries → read_zim_entry for details

🎯 **TYPICAL WORKFLOWS**:

**Research Workflow** (most common):
1. list_zim_files() → See available knowledge bases
2. search_zim_files(query="topic", max_results=10) → Find relevant articles
3. read_zim_entry(zim_file="...", entry_path=result.path) → Read full content

**Quick Answer Workflow**:
1. search_and_extract_content(query="question", max_results=3)
   → Get search results + content in one call

**Exploration Workflow**:
1. get_random_entries(count=10) → Discover interesting topics
2. read_zim_entry() → Deep dive on interesting finds

**Focused Research Workflow**:
1. list_zim_files() → Identify the right knowledge base
2. search_zim_files(query="specific topic", zim_files=["specific_file.zim"])
   → Search only relevant file
3. browse_zim_entries(zim_file="...", title_pattern="pattern")
   → Explore related entries

⚠️ **IMPORTANT NOTES**:
• ZIM files can be very large (Wikipedia is 90GB+) - be patient with searches
• Content truncation is automatic to prevent token overflow
• Search results are ranked by relevance
• Use pagination (start_offset) for browsing large result sets
• HTML content is automatically cleaned in 'text' format
• Entry paths from search results can be used directly in read_zim_entry

🚀 **PERFORMANCE TIPS**:
• Results are cached - repeated searches are faster
• Archives are kept open for performance
• Limit max_results to what you actually need
• Use specific file searches when you know the source
""",
)


@mcp.tool()
def list_zim_files() -> ListZimFilesResponse:
    """
    List all available ZIM files in the configured directory.

    Returns:
        Dictionary containing list of ZIM files with metadata
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
        return ListZimFilesResponse(status="error", count=0, files=[])


@mcp.tool()
def get_zim_metadata(zim_file: str) -> ZimFileMetadataResponse:
    """
    Get detailed metadata about a specific ZIM file.

    Args:
        zim_file: Name or path of the ZIM file

    Returns:
        Dictionary containing detailed ZIM file metadata
    """
    try:
        logger.info("Getting metadata for ZIM file: %s", zim_file)

        # Get file info
        file_info = zim_manager.get_zim_file_info(zim_file)

        if file_info is None:
            return ZimFileMetadataResponse(
                status="error",
                metadata=ZimMetadata(
                    filename="",
                    title="",
                    description="",
                    size=0,
                    size_formatted="",
                    article_count=0,
                    media_count=0,
                    language="",
                    creator="",
                    date="",
                    has_fulltext_index=False,
                    has_title_index=False,
                    uuid="",
                ),
                cache_info=CacheInfo(is_cached=False),
            )

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
        return ZimFileMetadataResponse(
            status="error",
            metadata=ZimMetadata(
                filename="",
                title="",
                description="",
                size=0,
                size_formatted="",
                article_count=0,
                media_count=0,
                language="",
                creator="",
                date="",
                has_fulltext_index=False,
                has_title_index=False,
                uuid="",
            ),
            cache_info=CacheInfo(is_cached=False),
        )


@mcp.tool()
def read_zim_entry(
    zim_file: str, entry_path: str, output_format: str = "text"
) -> ZimEntryResponse:
    """
    Read specific entry content from a ZIM file.

    Args:
        zim_file: Name or path of the ZIM file
        entry_path: Path to the entry in the ZIM file
        output_format: Output format (text, html, raw)

    Returns:
        Dictionary containing entry content and metadata
    """
    try:
        logger.info("Reading entry %s from %s", entry_path, zim_file)

        # Validate format
        if output_format not in ["text", "html", "raw"]:
            return ZimEntryResponse(
                status="error",
                entry=ZimEntryContent(
                    path="",
                    title="",
                    content="",
                    content_length=0,
                    format="",
                    is_redirect=False,
                ),
            )

        # Get entry
        entry = zim_manager.get_entry_by_path(zim_file, entry_path)

        if entry is None:
            return ZimEntryResponse(
                status="error",
                entry=ZimEntryContent(
                    path="",
                    title="",
                    content="",
                    content_length=0,
                    format="",
                    is_redirect=False,
                ),
            )

        # Get content
        item = entry.get_item()
        content_bytes = bytes(item.content)

        # Convert content based on format
        if output_format == "raw":
            # Return raw bytes as hex
            content = content_bytes.hex()
        else:
            # Decode as text
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode("latin-1")
                except UnicodeDecodeError:
                    content = str(content_bytes)

            # Clean HTML if text format requested
            if output_format == "text" and content:
                content = clean_html_content(content)

        # Truncate if too long
        if len(content) > config.max_content_length:
            content = content[: config.max_content_length] + "... [truncated]"

        return ZimEntryResponse(
            status="success",
            entry=ZimEntryContent(
                path=entry.path,
                title=entry.title,
                content=content,
                content_length=len(content_bytes),
                format=output_format,
                is_redirect=entry.is_redirect,
            ),
        )

    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as e:
        logger.error("Error reading entry %s from %s: %s", entry_path, zim_file, e)
        return ZimEntryResponse(
            status="error",
            entry=ZimEntryContent(
                path="",
                title="",
                content="",
                content_length=0,
                format="",
                is_redirect=False,
            ),
        )


@mcp.tool()
def search_zim_files(
    query: str,
    zim_files: Optional[List[str]] = None,
    max_results: int = 20,
    start_offset: int = 0,
) -> SearchResponse:
    """
    Search for content across one or multiple ZIM files.

    Args:
        query: Search query string
        zim_files: Optional list of specific ZIM files to search (default: all)
        max_results: Maximum number of results (default: 20)
        start_offset: Pagination offset (default: 0)

    Returns:
        Dictionary containing search results with titles, paths, and relevance scores
    """
    try:
        logger.info("Searching ZIM files for: %s", query)

        # Validate parameters
        if max_results <= 0 or max_results > config.max_search_results:
            return SearchResponse(
                status="error",
                query=query,
                count=0,
                results=[],
                pagination=SearchPagination(
                    start_offset=start_offset, max_results=max_results, has_more=False
                ),
            )

        if start_offset < 0:
            return SearchResponse(
                status="error",
                query=query,
                count=0,
                results=[],
                pagination=SearchPagination(
                    start_offset=start_offset, max_results=max_results, has_more=False
                ),
            )

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
        return SearchResponse(
            status="error",
            query=query,
            count=0,
            results=[],
            pagination=SearchPagination(
                start_offset=start_offset, max_results=max_results, has_more=False
            ),
        )


@mcp.tool()
def search_and_extract_content(
    query: str,
    zim_files: Optional[List[str]] = None,
    max_results: int = 10,
    content_format: str = "text",
    max_content_length: Optional[int] = None,
) -> SearchAndExtractResponse:
    """
    Search and return full content of matching entries.

    Args:
        query: Search query
        zim_files: Optional list of specific ZIM files
        max_results: Maximum results to extract content for
        content_format: Format for content (text, html)
        max_content_length: Maximum content length per entry

    Returns:
        Dictionary containing search results with full extracted content
    """
    try:
        logger.info("Searching and extracting content for: %s", query)

        # Validate parameters
        if content_format not in ["text", "html"]:
            return SearchAndExtractResponse(
                status="error", query=query, count=0, results=[], format=content_format
            )

        if max_results <= 0 or max_results > 50:
            return SearchAndExtractResponse(
                status="error", query=query, count=0, results=[], format=content_format
            )

        # Perform search
        if zim_files:
            search_results = search_engine.search_multiple_zim(
                zim_files, query, max_results, 0
            )
        else:
            search_results = search_engine.search_all_zim_files(query, max_results, 0)

        # Extract content for each result
        extracted_contents = content_extractor.extract_search_results_content(
            search_results, content_format
        )

        # Format results
        formatted_results = []
        for content in extracted_contents:
            # Apply content length limit if specified
            content_text = content.content
            if max_content_length and len(content_text) > max_content_length:
                content_text = content_text[:max_content_length] + "... [truncated]"

            formatted_results.append(
                ExtractedContent(
                    path=content.path,
                    title=content.title,
                    content=content_text,
                    content_type=content.content_type,
                    content_length=content.content_length,
                    preview=content.preview,
                    is_redirect=content.is_redirect,
                    metadata=content.metadata,
                )
            )

        return SearchAndExtractResponse(
            status="success",
            query=query,
            count=len(formatted_results),
            results=formatted_results,
            format=content_format,
        )

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error searching and extracting content for '%s': %s", query, e)
        return SearchAndExtractResponse(
            status="error", query=query, count=0, results=[], format=content_format
        )


@mcp.tool()
def browse_zim_entries(
    zim_file: str,
    path_pattern: Optional[str] = None,
    title_pattern: Optional[str] = None,
    limit: int = 50,
) -> BrowseResponse:
    """
    Browse entries by path patterns or title patterns.

    Args:
        zim_file: ZIM file to browse
        path_pattern: Optional path pattern to match
        title_pattern: Optional title pattern to match
        limit: Maximum entries to return

    Returns:
        Dictionary containing list of matching entries with basic info
    """
    try:
        logger.info("Browsing entries in %s", zim_file)

        # Validate parameters
        if limit <= 0 or limit > 200:
            return BrowseResponse(
                status="error",
                zim_file=zim_file,
                path_pattern=path_pattern,
                title_pattern=title_pattern,
                count=0,
                entries=[],
            )

        # Validate ZIM file
        if not zim_manager.validate_zim_file(zim_file):
            return BrowseResponse(
                status="error",
                zim_file=zim_file,
                path_pattern=path_pattern,
                title_pattern=title_pattern,
                count=0,
                entries=[],
            )

        # Browse entries
        results = search_engine.browse_entries_by_pattern(
            zim_file, path_pattern, title_pattern, limit
        )

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append(
                BrowsedEntry(
                    path=result.path, title=result.title, is_redirect=result.is_redirect
                )
            )

        return BrowseResponse(
            status="success",
            zim_file=zim_file,
            path_pattern=path_pattern,
            title_pattern=title_pattern,
            count=len(formatted_results),
            entries=formatted_results,
        )

    except (ValueError, RuntimeError, OSError) as e:
        logger.error("Error browsing entries in %s: %s", zim_file, e)
        return BrowseResponse(
            status="error",
            zim_file=zim_file,
            path_pattern=path_pattern,
            title_pattern=title_pattern,
            count=0,
            entries=[],
        )


@mcp.tool()
def get_random_entries(
    zim_files: Optional[List[str]] = None, count: int = 5
) -> RandomEntriesResponse:
    """
    Get random entries from ZIM files for exploration.

    Args:
        zim_files: Optional list of specific ZIM files (default: all available)
        count: Number of random entries to return

    Returns:
        Dictionary containing random entries with basic info
    """
    try:
        logger.info("Getting %d random entries", count)

        # Validate count
        if count <= 0 or count > 50:
            return RandomEntriesResponse(status="error", count=0, entries=[])

        # Get available files if none specified
        if zim_files is None:
            available_files = zim_manager.discover_zim_files()
            zim_files = [f.filename for f in available_files]

        if not zim_files:
            return RandomEntriesResponse(status="error", count=0, entries=[])

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
        return RandomEntriesResponse(status="error", count=0, entries=[])


# Resource endpoints
@mcp.resource("zim://files")
def list_zim_files_resource() -> str:
    """Provide list of available ZIM files as a resource"""
    try:
        result = list_zim_files()
        if result.status == "success":
            return json.dumps(result.files, indent=2)
        else:
            return f"Error: {result}"
    except (ValueError, RuntimeError, OSError, TypeError) as e:
        return f"Error: {str(e)}"


@mcp.resource("zim://file/{filename}/metadata")
def get_zim_metadata_resource(filename: str) -> str:
    """Provide ZIM file metadata as a resource"""
    try:
        result = get_zim_metadata(filename)
        if result.status == "success":
            return json.dumps(result.metadata, indent=2)
        else:
            return f"Error: {result}"
    except (ValueError, RuntimeError, OSError, TypeError) as e:
        return f"Error: {str(e)}"


@mcp.resource("zim://file/{filename}/entry/{path}")
def read_zim_entry_resource(filename: str, path: str) -> str:
    """Provide specific entry content as a resource"""
    try:
        result = read_zim_entry(filename, path, output_format="text")
        if result.status == "success":
            return result.entry.content
        else:
            return f"Error: {result}"
    except (ValueError, RuntimeError, OSError, UnicodeDecodeError, TypeError) as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
