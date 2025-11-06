import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import libzim.reader  # pyright: ignore[reportMissingModuleSource]
from .config import ZimServerConfig
from .utils import LRUCache, validate_zim_file_path, format_file_size, timing_decorator


@dataclass
class ZimManagerFileInfo:
    """Information about a ZIM file"""

    filename: str
    filepath: Path
    size: int
    size_formatted: str
    article_count: int
    media_count: int
    title: str
    description: str
    language: str
    creator: str
    date: str
    has_fulltext_index: bool
    has_title_index: bool
    uuid: str


class ZimManager:
    """Manages ZIM file operations and caching"""

    def __init__(self, config: ZimServerConfig):
        self.config = config
        self.logger = logging.getLogger("mcp_zim_server.zim_manager")

        # Cache for open archives
        self.archive_cache = LRUCache(config.archive_cache_size)

        # Cache for file info
        self.file_info_cache: Dict[str, ZimManagerFileInfo] = {}

        # Track available ZIM files
        self._available_files: Optional[List[ZimManagerFileInfo]] = None

    @timing_decorator
    def discover_zim_files(
        self, force_refresh: bool = False
    ) -> List[ZimManagerFileInfo]:
        """Discover all ZIM files in the configured directory (recursively)"""
        if self._available_files is not None and not force_refresh:
            return self._available_files

        self.logger.info(
            "Recursively discovering ZIM files in %s", self.config.zim_files_directory
        )

        zim_files = []
        zim_directory = self.config.zim_files_directory

        if not zim_directory.exists():
            self.logger.warning("ZIM files directory does not exist: %s", zim_directory)
            return []

        # Find all .zim files recursively (supports nested folder structures)
        for zim_file in zim_directory.rglob("*.zim"):
            try:
                file_info = self._get_zim_file_info(zim_file)
                zim_files.append(file_info)
                self.logger.debug("Processed ZIM file: %s", file_info.filename)
            except Exception as e:  # (OSError, RuntimeError, ValueError)
                self.logger.error("Error reading ZIM file %s: %s", zim_file, e)
                continue

        self._available_files = zim_files
        self.logger.info("Discovered %d ZIM files", len(zim_files))
        return zim_files

    def _get_zim_file_info(self, filepath: Path) -> ZimManagerFileInfo:
        """Get information about a ZIM file"""
        filename = filepath.name

        # Check cache first
        if filename in self.file_info_cache:
            return self.file_info_cache[filename]

        try:
            # Check file size before opening (prevent loading massive files)
            preliminary_size = filepath.stat().st_size
            size_mb = preliminary_size / (1024 * 1024)

            # Skip metadata loading for files exceeding size limit
            if size_mb > self.config.max_zim_file_size_mb:
                self.logger.info(
                    "Skipping metadata load for %s (%.1f MB > %d MB limit) - file too large",
                    filename,
                    size_mb,
                    self.config.max_zim_file_size_mb,
                )

                # Return minimal metadata without opening archive
                file_info = ZimManagerFileInfo(
                    filename=filename,
                    filepath=filepath,
                    size=preliminary_size,
                    size_formatted=format_file_size(preliminary_size),
                    article_count=0,
                    media_count=0,
                    title=filename,
                    description=f"Large ZIM file (skipped metadata loading due to size)",
                    language="",
                    creator="",
                    date="",
                    has_fulltext_index=False,
                    has_title_index=False,
                    uuid="",
                )

                # Cache the info
                self.file_info_cache[filename] = file_info
                return file_info

            # Open archive to read metadata (for files within size limit)
            archive = libzim.reader.Archive(str(filepath))
            # Get file size (handles multipart archives correctly)
            file_size = archive.filesize

            # Verify archive integrity if checksum is available
            if archive.has_checksum:
                if not archive.check():
                    self.logger.warning(
                        "Checksum verification failed for %s - file may be corrupted",
                        filename,
                    )

            # Extract metadata
            metadata = {}
            for key in archive.metadata_keys:
                try:
                    metadata[key] = archive.get_metadata(key)
                except (KeyError, ValueError):
                    metadata[key] = ""

            file_info = ZimManagerFileInfo(
                filename=filename,
                filepath=filepath,
                size=file_size,
                size_formatted=format_file_size(file_size),
                article_count=archive.article_count,
                media_count=archive.media_count,
                title=metadata.get("Title", filename),
                description=metadata.get("Description", ""),
                language=metadata.get("Language", ""),
                creator=metadata.get("Creator", ""),
                date=metadata.get("Date", ""),
                has_fulltext_index=archive.has_fulltext_index,
                has_title_index=archive.has_title_index,
                uuid=str(archive.uuid),
            )

            # Cache the info
            self.file_info_cache[filename] = file_info
            return file_info

        except (OSError, RuntimeError, ValueError) as e:
            self.logger.error("Error reading ZIM file metadata %s: %s", filepath, e)
            raise

    def get_zim_file_info(self, filename: str) -> Optional[ZimManagerFileInfo]:
        """Get information about a specific ZIM file"""
        try:
            filepath = validate_zim_file_path(filename, self.config.zim_files_directory)

            if not filepath.exists():
                return None

            return self._get_zim_file_info(filepath)

        except (OSError, RuntimeError, ValueError) as e:
            self.logger.error("Error getting ZIM file info for %s: %s", filename, e)
            return None

    def get_archive(self, filename: str) -> Optional[libzim.reader.Archive]:
        """Get an open ZIM archive, using cache when possible"""
        try:
            # Validate file path
            filepath = validate_zim_file_path(filename, self.config.zim_files_directory)

            if not filepath.exists():
                self.logger.error("ZIM file not found: %s", filepath)
                return None

            # Check cache
            cache_key = str(filepath)
            cached_archive = self.archive_cache.get(cache_key)

            if cached_archive is not None:
                self.logger.debug("Using cached archive for %s", filename)
                return cached_archive

            # Open new archive
            self.logger.debug("Opening new archive for %s", filename)
            archive = libzim.reader.Archive(str(filepath))

            # Cache the archive
            self.archive_cache.put(cache_key, archive)

            return archive

        except (OSError, RuntimeError, ValueError) as e:
            self.logger.error("Error opening ZIM archive %s: %s", filename, e)
            return None

    def get_entry_by_path(
        self, filename: str, entry_path: str
    ) -> Optional[libzim.reader.Entry]:
        """Get an entry from a ZIM file by path"""
        try:
            archive = self.get_archive(filename)
            if archive is None:
                return None

            if not archive.has_entry_by_path(entry_path):
                return None

            return archive.get_entry_by_path(entry_path)

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            self.logger.error(
                "Error getting entry %s from %s: %s", entry_path, filename, e
            )
            return None

    def get_entry_by_title(
        self, filename: str, title: str
    ) -> Optional[libzim.reader.Entry]:
        """Get an entry from a ZIM file by title"""
        try:
            archive = self.get_archive(filename)
            if archive is None:
                return None

            if not archive.has_entry_by_title(title):
                return None

            return archive.get_entry_by_title(title)

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            self.logger.error(
                "Error getting entry by title '%s' from %s: %s", title, filename, e
            )
            return None

    def get_main_entry(self, filename: str) -> Optional[libzim.reader.Entry]:
        """Get the main entry of a ZIM file"""
        try:
            archive = self.get_archive(filename)
            if archive is None:
                return None

            if not archive.has_main_entry:
                return None

            return archive.main_entry

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            self.logger.error("Error getting main entry from %s: %s", filename, e)
            return None

    def get_random_entry(self, filename: str) -> Optional[libzim.reader.Entry]:
        """Get a random entry from a ZIM file"""
        try:
            archive = self.get_archive(filename)
            if archive is None:
                return None

            return archive.get_random_entry()

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            self.logger.error("Error getting random entry from %s: %s", filename, e)
            return None

    def validate_zim_file(self, filename: str) -> bool:
        """Validate that a ZIM file exists and is readable"""
        try:
            filepath = validate_zim_file_path(filename, self.config.zim_files_directory)

            if not filepath.exists():
                return False

            # Try to open the archive
            archive = self.get_archive(filename)
            return archive is not None

        except (OSError, RuntimeError, ValueError):
            return False

    def clear_caches(self) -> None:
        """Clear all caches"""
        self.archive_cache.clear()
        self.file_info_cache.clear()
        self._available_files = None
        self.logger.info("Cleared all caches")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "archive_cache_size": self.archive_cache.size(),
            "archive_cache_max_size": self.config.archive_cache_size,
            "file_info_cache_size": len(self.file_info_cache),
            "available_files_cached": self._available_files is not None,
        }
