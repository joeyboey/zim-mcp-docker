import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import libzim.search  # pyright: ignore[reportMissingModuleSource]
from .config import ZimServerConfig
from .zim_manager import ZimManager
from .utils import LRUCache, validate_search_query, timing_decorator


@dataclass
class SearchEngineResult:
    """Search result from ZIM file"""

    zim_file: str
    path: str
    title: str
    score: float = 0.0
    preview: str = ""
    is_redirect: bool = False


class SearchEngine:
    """Search engine for ZIM files"""

    def __init__(self, config: ZimServerConfig, zim_manager: ZimManager):
        self.config = config
        self.zim_manager = zim_manager
        self.logger = logging.getLogger("mcp_zim_server.search_engine")

        # Cache for search results
        self.search_cache = LRUCache(config.search_cache_size)

        # Cache for searchers
        self.searcher_cache: Dict[str, libzim.search.Searcher] = {}

    def _get_searcher(self, zim_file: str) -> Optional[libzim.search.Searcher]:
        """Get or create a searcher for a ZIM file"""
        try:
            if zim_file in self.searcher_cache:
                return self.searcher_cache[zim_file]

            archive = self.zim_manager.get_archive(zim_file)
            if archive is None:
                return None

            # Check if archive has search index
            if not archive.has_fulltext_index:
                self.logger.warning(
                    "ZIM file %s does not have a fulltext index", zim_file
                )
                return None

            searcher = libzim.search.Searcher(archive)
            self.searcher_cache[zim_file] = searcher

            return searcher

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error("Error creating searcher for %s: %s", zim_file, e)
            return None

    @timing_decorator
    def search_single_zim(
        self, zim_file: str, query: str, max_results: int = 20, start_offset: int = 0
    ) -> List[SearchEngineResult]:
        """Search within a single ZIM file"""
        try:
            # Validate query
            clean_query = validate_search_query(query)

            # Get searcher
            searcher = self._get_searcher(zim_file)
            if searcher is None:
                self.logger.warning("Cannot search %s: no searcher available", zim_file)
                return []

            # Create search query
            search_query = libzim.search.Query().set_query(clean_query)

            # Perform search
            search = searcher.search(search_query)

            # Get results
            result_set = search.getResults(start_offset, max_results)

            results = []
            archive = self.zim_manager.get_archive(zim_file)

            for path in result_set:
                try:
                    entry = archive.get_entry_by_path(path)
                    if entry:
                        result = SearchEngineResult(
                            zim_file=zim_file,
                            path=path,
                            title=entry.title,
                            is_redirect=entry.is_redirect,
                        )
                        results.append(result)
                except (KeyError, ValueError, RuntimeError) as e:
                    self.logger.warning(
                        "Error processing search result %s: %s", path, e
                    )
                    continue

            self.logger.debug(
                "Found %d results in %s for query: %s",
                len(results),
                zim_file,
                clean_query,
            )
            return results

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error("Error searching %s for '%s': %s", zim_file, query, e)
            return []

    @timing_decorator
    def search_multiple_zim(
        self,
        zim_files: List[str],
        query: str,
        max_results: int = 20,
        start_offset: int = 0,
    ) -> List[SearchEngineResult]:
        """Search across multiple ZIM files"""
        try:
            # Validate query
            clean_query = validate_search_query(query)

            # Check cache
            cache_key = f"{','.join(sorted(zim_files))}|{clean_query}|{max_results}|{start_offset}"
            cached_results = self.search_cache.get(cache_key)
            if cached_results is not None:
                self.logger.debug("Using cached search results for: %s", clean_query)
                return cached_results

            all_results = []

            if self.config.enable_parallel_search and len(zim_files) > 1:
                # Parallel search (simplified for now)
                for zim_file in zim_files:
                    file_results = self.search_single_zim(
                        zim_file, clean_query, max_results, 0
                    )
                    all_results.extend(file_results)
            else:
                # Sequential search
                for zim_file in zim_files:
                    file_results = self.search_single_zim(
                        zim_file, clean_query, max_results, 0
                    )
                    all_results.extend(file_results)

            # Sort results by relevance (basic implementation)
            # For now, just sort by title length as a simple relevance metric
            all_results.sort(key=lambda r: len(r.title))

            # Apply pagination
            paginated_results = all_results[start_offset : start_offset + max_results]

            # Cache results
            self.search_cache.put(cache_key, paginated_results)

            self.logger.info(
                "Search for '%s' returned %d results",
                clean_query,
                len(paginated_results),
            )
            return paginated_results

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error(
                "Error searching multiple ZIM files for '%s': %s", query, e
            )
            return []

    def search_all_zim_files(
        self, query: str, max_results: int = 20, start_offset: int = 0
    ) -> List[SearchEngineResult]:
        """Search across all available ZIM files"""
        try:
            # Get all available ZIM files
            zim_files_info = self.zim_manager.discover_zim_files()

            # Filter to only files with fulltext index
            searchable_files = []
            for file_info in zim_files_info:
                if file_info.has_fulltext_index:
                    searchable_files.append(file_info.filename)
                else:
                    self.logger.debug(
                        "Skipping %s: no fulltext index", file_info.filename
                    )

            if not searchable_files:
                self.logger.warning(
                    "No ZIM files with fulltext index available for search"
                )
                return []

            self.logger.info(
                "Searching %d ZIM files with fulltext index", len(searchable_files)
            )
            return self.search_multiple_zim(
                searchable_files, query, max_results, start_offset
            )

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error("Error searching all ZIM files for '%s': %s", query, e)
            return []

    def get_estimated_matches(self, zim_file: str, query: str) -> int:
        """Get estimated number of matches for a query"""
        try:
            clean_query = validate_search_query(query)

            searcher = self._get_searcher(zim_file)
            if searcher is None:
                return 0

            search_query = libzim.search.Query().set_query(clean_query)
            search = searcher.search(search_query)

            return search.getEstimatedMatches()

        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error("Error getting estimated matches for %s: %s", zim_file, e)
            return 0

    def clear_caches(self) -> None:
        """Clear all search caches"""
        self.search_cache.clear()
        self.searcher_cache.clear()
        self.logger.info("Cleared search caches")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get search cache statistics"""
        return {
            "search_cache_size": self.search_cache.size(),
            "search_cache_max_size": self.config.search_cache_size,
            "searcher_cache_size": len(self.searcher_cache),
        }
