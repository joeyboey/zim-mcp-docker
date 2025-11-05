"""
MCP ZIM Server - Offline search capabilities for LLMs using ZIM files

This package provides an MCP (Model Context Protocol) server that enables
Large Language Models to access and search offline knowledge bases stored
in ZIM file format.
"""

__version__ = "0.2.0"
__description__ = "MCP server providing offline search capabilities through ZIM files"

# Configuration
from .config import ZimServerConfig, load_config

# Data Models
from .models import (
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

# Core Components
from .zim_manager import ZimManager, ZimManagerFileInfo
from .search_engine import SearchEngine, SearchEngineResult
from .content_extractor import ContentExtractor, ExtractedContentInfo
from .file_discovery import FileDiscovery

# Utilities
from .utils import (
    setup_logging,
    timing_decorator,
    sanitize_filename,
    validate_zim_file_path,
    format_file_size,
    truncate_text,
    clean_html_content,
    generate_cache_key,
    safe_get_dict_value,
    LRUCache,
    validate_search_query,
    extract_text_preview,
)

__all__ = [
    # Metadata
    "__version__",
    "__description__",
    # Configuration
    "ZimServerConfig",
    "load_config",
    # Models
    "ZimFileInfo",
    "ZimMetadata",
    "CacheInfo",
    "ZimFileMetadataResponse",
    "ZimEntryContent",
    "ZimEntryResponse",
    "SearchResult",
    "SearchPagination",
    "SearchResponse",
    "ExtractedContent",
    "SearchAndExtractResponse",
    "BrowsedEntry",
    "BrowseResponse",
    "RandomEntry",
    "RandomEntriesResponse",
    "ListZimFilesResponse",
    # Core Components
    "ZimManager",
    "ZimManagerFileInfo",
    "SearchEngine",
    "SearchEngineResult",
    "ContentExtractor",
    "ExtractedContentInfo",
    "FileDiscovery",
    # Utilities
    "setup_logging",
    "timing_decorator",
    "sanitize_filename",
    "validate_zim_file_path",
    "format_file_size",
    "truncate_text",
    "clean_html_content",
    "generate_cache_key",
    "safe_get_dict_value",
    "LRUCache",
    "validate_search_query",
    "extract_text_preview",
]
