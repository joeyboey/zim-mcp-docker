from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# Pydantic Models for structured responses
class ZimFileInfo(BaseModel):
    filename: str
    title: str
    description: str
    size: str
    article_count: int
    media_count: int
    language: str
    creator: str
    date: str
    has_fulltext_index: bool
    has_title_index: bool


class ZimMetadata(BaseModel):
    filename: str
    title: str
    description: str
    size: int
    size_formatted: str
    article_count: int
    media_count: int
    language: str
    creator: str
    date: str
    has_fulltext_index: bool
    has_title_index: bool
    uuid: str


class CacheInfo(BaseModel):
    is_cached: bool


class ZimFileMetadataResponse(BaseModel):
    status: str
    metadata: ZimMetadata
    cache_info: CacheInfo


class ZimEntryContent(BaseModel):
    path: str
    title: str
    content: str
    content_length: int
    format: str
    mime_type: str
    processing_time_ms: float
    is_redirect: bool


class ZimEntryResponse(BaseModel):
    status: str
    entry: ZimEntryContent


class SearchResult(BaseModel):
    zim_file: str
    path: str
    title: str
    score: float
    preview: str
    is_redirect: bool


class SearchPagination(BaseModel):
    start_offset: int
    max_results: int
    has_more: bool


class SearchResponse(BaseModel):
    status: str
    query: str
    count: int
    results: List[SearchResult]
    pagination: SearchPagination


class RandomEntry(BaseModel):
    zim_file: str
    path: str
    title: str
    is_redirect: bool


class RandomEntriesResponse(BaseModel):
    status: str
    count: int
    entries: List[RandomEntry]


class ListZimFilesResponse(BaseModel):
    status: str
    count: int
    files: List[ZimFileInfo]
