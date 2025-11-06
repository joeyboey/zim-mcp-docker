import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ZimServerConfig:
    """Configuration settings for the ZIM server"""

    # Directory containing ZIM files
    zim_files_directory: Path

    # Search settings
    max_search_results: int = 100
    search_timeout: int = 30
    default_content_format: str = "text"
    max_content_length: int = 50000

    # Cache settings
    archive_cache_size: int = 10  # Number of archives to keep open
    search_cache_size: int = 1000  # Number of search results to cache

    # Performance settings
    max_concurrent_searches: int = 5
    enable_parallel_search: bool = True

    # Logging settings
    log_level: str = "INFO"
    enable_performance_logging: bool = False


def load_config() -> ZimServerConfig:
    """Load configuration from environment variables and defaults"""

    # Get ZIM files directory from environment or use default
    zim_dir = os.getenv("ZIM_FILES_DIRECTORY", "./zim_files")
    zim_files_directory = Path(zim_dir).resolve()

    # Ensure directory exists
    zim_files_directory.mkdir(parents=True, exist_ok=True)

    return ZimServerConfig(
        zim_files_directory=zim_files_directory,
        max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "100")),
        search_timeout=int(os.getenv("SEARCH_TIMEOUT", "30")),
        default_content_format=os.getenv("DEFAULT_CONTENT_FORMAT", "text"),
        max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", "50000")),
        archive_cache_size=int(os.getenv("ARCHIVE_CACHE_SIZE", "10")),
        search_cache_size=int(os.getenv("SEARCH_CACHE_SIZE", "1000")),
        max_concurrent_searches=int(os.getenv("MAX_CONCURRENT_SEARCHES", "5")),
        enable_parallel_search=os.getenv("ENABLE_PARALLEL_SEARCH", "true").lower()
        == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        enable_performance_logging=os.getenv(
            "ENABLE_PERFORMANCE_LOGGING", "false"
        ).lower()
        == "true",
    )


# Global configuration instance
config = load_config()
