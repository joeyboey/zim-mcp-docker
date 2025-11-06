# MCP ZIM Server

An MCP (Model Context Protocol) server that provides offline search and content extraction capabilities for Large Language Models (LLMs) using ZIM files. This server allows LLMs to perform deep research and access information in offline environments, replacing the need for live web access.

## Features

- **Offline Search**: Full-text search across millions of articles within ZIM files.
- **Intelligent Content Processing**: Automatic HTML-to-Markdown conversion with MIME-aware processing for different content types.
- **Image Support**: Direct image display via ImageContent for agent interfaces.
- **ZIM File Discovery**: Automatically discover ZIM files in a specified directory.
- **Multi-level Caching**: Archive caching, search result caching, and file info caching for optimal performance.
- **Multiple Transports**: Support for stdio, HTTP (streamable), and SSE protocols.
- **Configurable**: Easily configurable through environment variables.

## Requirements

- Docker and Docker Compose
- ZIM files (Wikipedia dumps or other offline content)

### ZIM Sources
- https://dumps.wikimedia.org/other/kiwix/zim
- https://download.kiwix.org/zim/

## Getting Started

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/joeyboey/zim-mcp-docker.git
cd zim-mcp-docker

# Place your ZIM files in the zim_files directory
mkdir -p zim_files
# Copy your .zim files to zim_files/

# Start the server
docker compose up --build
```

The server will be available at:
- HTTP (Streamable): `http://localhost:8000/mcp/`
- SSE: `http://localhost:8001/sse`
- Health checks: `http://localhost:8000/health` and `http://localhost:8001/health`

## Docker Configuration

The server supports two transport protocols running simultaneously:

- **HTTP (Streamable)** - Port 8000 (recommended for modern MCP clients)
- **SSE** - Port 8001 (for legacy clients and Home Assistant)

### Environment Variables

Configure the server using environment variables in `compose.yaml` or `.env` file:

#### ZIM Server Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ZIM_FILES_DIRECTORY` | Directory containing ZIM files (absolute path in container) | `/app/zim_files` | `/app/zim_files` |
| `MAX_SEARCH_RESULTS` | Maximum number of search results to return per query | `100` | `100`, `200` |
| `SEARCH_TIMEOUT` | Timeout for search operations in seconds | `30` | `30`, `60` |
| `MAX_CONTENT_LENGTH` | Maximum content length in characters (prevents token overflow) | `50000` | `50000`, `100000` |
| `LOG_LEVEL` | Logging level for ZIM server | `INFO` | `DEBUG`, `INFO`, `WARNING` |

#### Cache Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ARCHIVE_CACHE_SIZE` | Number of ZIM files to keep open simultaneously (LRU cache) | `10` | `10`, `20` |
| `SEARCH_CACHE_SIZE` | Number of search result sets to cache (LRU cache) | `1000` | `1000`, `2000` |

**Note**: `ARCHIVE_CACHE_SIZE=10` means the server keeps up to 10 ZIM files open at once. When an 11th file is accessed, the least recently used file is closed. This significantly improves performance for frequently accessed files.

#### Performance Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DEFAULT_CONTENT_FORMAT` | Default format for content extraction | `text` | `text`, `html` |
| `MAX_CONCURRENT_SEARCHES` | Maximum number of concurrent search operations | `5` | `5`, `10` |
| `ENABLE_PARALLEL_SEARCH` | Enable parallel search across multiple ZIM files | `true` | `true`, `false` |
| `ENABLE_PERFORMANCE_LOGGING` | Enable detailed performance logging | `false` | `true`, `false` |
| `MAX_ZIM_FILE_SIZE_MB` | Maximum ZIM file size in MB to load metadata for (larger files skipped to save resources) | `1000` | `500`, `1000`, `2000` |

#### FastMCP Transport Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `FASTMCP_TRANSPORT` | MCP transport protocol | `stdio` | `http`, `sse`, `stdio` |
| `FASTMCP_HOST` | Host address to bind to (for http/sse transports) | `0.0.0.0` | `0.0.0.0`, `127.0.0.1` |
| `FASTMCP_PORT` | Port to bind to (for http/sse transports) | `8000` | `8000`, `8001` |
| `FASTMCP_LOG_LEVEL` | Logging level for FastMCP framework | `INFO` | `DEBUG`, `INFO`, `WARNING` |

See `compose.yaml` for a complete working configuration example.

## Configuration Reference

For detailed environment variable configuration, see the [Environment Variables](#environment-variables) section under Docker Configuration above.

**Quick Reference**: All configuration is done via environment variables. The `compose.yaml` file contains a complete working configuration with all available options.

## Tools

### `list_zim_files`

Lists all available ZIM files in the configured directory.

-   list_zim_files()
    -   **Parameters**: None
    -   **Returns**: A dictionary containing a list of ZIM files with their metadata.

### `get_zim_metadata`

Gets detailed metadata about a specific ZIM file.

- get_zim_metadata(zim_file: str)
    -   **Parameters**:
        -   `zim_file` (str): The name of the ZIM file.
    -   **Returns**: A dictionary containing detailed metadata for the specified ZIM file.

### `get_main_entry`

Gets the main entry (homepage) of a ZIM file.

- get_main_entry(zim_file: str, raw_output: bool = False, return_markdown_only: bool = True)
    -   **Parameters**:
        -   `zim_file` (str): The name of the ZIM file.
        -   `raw_output` (bool): If True, returns original content without processing. (Default: False)
        -   `return_markdown_only` (bool): If True, returns only markdown text for chat rendering. (Default: True)
    -   **Returns**: The main/homepage entry content. For Wikipedia ZIMs, this is typically the Wikipedia homepage.

### `search_zim_files`

Searches for content across one or multiple ZIM files.

- search_zim_files(query: str, zim_files: Optional[List[str]], max_results: int, start_offset: int)
    -   **Parameters**:
        -   `query` (str): The search query.
        -   `zim_files` (Optional[List[str]]): A list of ZIM files to search. If not provided, all files are searched.
        -   `max_results` (int): The maximum number of results to return. (Default: 20)
        -   `start_offset` (int): The pagination offset. (Default: 0)
    -   **Returns**: A dictionary containing the search results.

### `read_zim_entry`

Reads and processes content from a ZIM file entry.

- read_zim_entry(zim_file: str, entry_path: str, raw_output: bool = False, return_markdown_only: bool = True)
    -   **Parameters**:
        -   `zim_file` (str): The name of the ZIM file.
        -   `entry_path` (str): The path to the entry.
        -   `raw_output` (bool): If True, returns original content without processing. (Default: False)
        -   `return_markdown_only` (bool): If True, returns only markdown text for chat rendering. (Default: True)
    -   **Returns**: Markdown string (if return_markdown_only=True), ZimEntryResponse (structured), or ImageContent (for images).





### `get_random_entries`

Gets a specified number of random entries from ZIM files.

- get_random_entries(zim_files: Optional[List[str]], count: int)
    -   **Parameters**:
        -   `zim_files` (Optional[List[str]]): A list of ZIM files to get entries from.
        -   `count` (int): The number of random entries to return.
    -   **Returns**: A list of random entries.

## Resource Endpoints

The server also exposes the following resource endpoints:

-   `zim://files`: Lists all available ZIM files.
-   `zim://{filename}/metadata`: Provides metadata for a specific ZIM file.
-   `zim://{filename}/entry/{path}`: Provides the content of a specific entry.

## Docker Usage

### Starting the Services

```bash
# Start both HTTP and SSE services
docker compose up --build

# Start only HTTP service
docker compose up zim-mcp-http

# Start only SSE service
docker compose up zim-mcp-sse

# Run in background
docker compose up -d
```

### Viewing Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f zim-mcp-http
docker compose logs -f zim-mcp-sse
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Managing ZIM Files

1.  **Place your ZIM files** in the `./zim_files` directory (or configure a different path in `compose.yaml`).

2.  **The server will automatically discover** all `.zim` files in the directory and subdirectories.

3.  **Restart the container** if you add new ZIM files:

    ```bash
    docker compose restart
    ```

### Accessing the Server

The Docker containers expose the following endpoints:

- **HTTP (Streamable)**: `http://localhost:8000/mcp/`
- **SSE**: `http://localhost:8001/sse`
- **Health Check (HTTP)**: `http://localhost:8000/health`
- **Health Check (SSE)**: `http://localhost:8001/health`

You can integrate with OpenWeb-UI, Claude Desktop, or any MCP-compatible client using these endpoints.

### Transport Protocols

The server supports multiple MCP transport protocols:

**Streamable HTTP** (Port 8000 - Recommended)

Enables streaming responses over JSON RPC via HTTP POST requests. See the [spec](https://modelcontextprotocol.io/specification/draft/basic/transports#streamable-http) for more details.

- Endpoint: `http://localhost:8000/mcp/`
- Best for modern MCP clients
- Supports full streaming capabilities

**Server-Sent Events (SSE)** (Port 8001 - Legacy)

> [!WARNING]
> The MCP community considers this a legacy transport protocol intended for backwards compatibility. [Streamable HTTP](#streamable-http) is the recommended replacement.

SSE transport enables server-to-client streaming. See the [spec](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse) for more details.

- Endpoint: `http://localhost:8001/sse`
- For legacy clients and Home Assistant
- Maintained for backwards compatibility

## Integrations

### Claude Desktop, Roo Code, etc.

To integrate with MCP clients, configure them to connect to the HTTP endpoint:

- **Endpoint**: `http://localhost:8000/mcp/`
- **Transport**: HTTP (Streamable)

Refer to your MCP client's documentation for specific configuration instructions for HTTP-based MCP servers.

## Development

Contributions are welcome! If you want to contribute to the development of the MCP ZIM Server, please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and write tests.
4.  Submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
