"""
Web tools for OpenCode.

Includes:
- WebSearch: Search the web using Exa API
- WebFetch: Fetch and parse web page content
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Any, Literal
from dataclasses import dataclass
from enum import Enum

from .tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


# Configuration constants
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB


class LiveCrawlMode(str, Enum):
    """Live crawl mode for web search."""
    FALLBACK = "fallback"
    PREFERRED = "preferred"


class SearchType(str, Enum):
    """Search type for web search."""
    AUTO = "auto"
    FAST = "fast"
    DEEP = "deep"


class WebFormat(str, Enum):
    """Output format for web fetch."""
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"


@dataclass
class WebSearchToolConfig:
    """Configuration for WebSearchTool."""
    base_url: str = "https://mcp.exa.ai"
    default_num_results: int = 8
    default_timeout_seconds: int = 25


@dataclass
class WebFetchToolConfig:
    """Configuration for WebFetchTool."""
    default_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_timeout_seconds: int = MAX_TIMEOUT_SECONDS
    max_response_size: int = MAX_RESPONSE_SIZE
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class WebSearchTool(BaseTool):
    """Tool for searching the web."""
    
    def __init__(self, config: Optional[WebSearchToolConfig] = None):
        self.config = config or WebSearchToolConfig()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="websearch",
            description="Search the web for information",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Web search query",
                    required=True,
                ),
                ToolParameter(
                    name="numResults",
                    type="number",
                    description=f"Number of search results to return (default: {self.config.default_num_results})",
                    required=False,
                ),
                ToolParameter(
                    name="livecrawl",
                    type="string",
                    description="Live crawl mode - 'fallback' or 'preferred'",
                    required=False,
                    enum=["fallback", "preferred"],
                ),
                ToolParameter(
                    name="type",
                    type="string",
                    description="Search type - 'auto', 'fast', or 'deep'",
                    required=False,
                    enum=["auto", "fast", "deep"],
                ),
                ToolParameter(
                    name="contextMaxCharacters",
                    type="number",
                    description="Maximum characters for context string optimized for LLMs (default: 10000)",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        query = kwargs.get("query")
        num_results = kwargs.get("numResults", self.config.default_num_results)
        livecrawl = kwargs.get("livecrawl", "fallback")
        search_type = kwargs.get("type", "auto")
        context_max_chars = kwargs.get("contextMaxCharacters")
        
        if not query:
            return ToolResult(
                tool_name="websearch",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: query",
            )
        
        try:
            # Request permission
            await ctx.ask(
                permission="websearch",
                patterns=[query],
                always=["*"],
                metadata={
                    "query": query,
                    "numResults": num_results,
                    "livecrawl": livecrawl,
                    "type": search_type,
                    "contextMaxCharacters": context_max_chars,
                },
            )
            
            # Build search request
            search_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "web_search_exa",
                    "arguments": {
                        "query": query,
                        "type": search_type,
                        "numResults": num_results,
                        "livecrawl": livecrawl,
                        "contextMaxCharacters": context_max_chars,
                    },
                },
            }
            
            # Make request
            headers = {
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            }
            
            url = f"{self.config.base_url}/mcp"
            
            timeout = asyncio.Timeout(self.config.default_timeout_seconds)
            
            try:
                async with asyncio.timeout(self.config.default_timeout_seconds):
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=search_request) as response:
                            if not response.ok:
                                error_text = await response.text()
                                raise RuntimeError(f"Search error ({response.status}): {error_text}")
                            
                            response_text = await response.text()
            
            except asyncio.TimeoutError:
                return ToolResult(
                    tool_name="websearch",
                    status=ToolStatus.ERROR,
                    content=None,
                    error="Search request timed out",
                )
            
            # Parse SSE response
            result_text = "No search results found. Please try a different query."
            
            for line in response_text.split("\n"):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if "result" in data and "content" in data["result"]:
                            content_list = data["result"]["content"]
                            if content_list and len(content_list) > 0:
                                result_text = content_list[0].get("text", result_text)
                                break
                    except json.JSONDecodeError:
                        continue
            
            return ToolResult(
                tool_name="websearch",
                status=ToolStatus.SUCCESS,
                content=result_text,
                title=f"Web search: {query}",
                metadata={},
            )
            
        except ImportError:
            # aiohttp not available, return error
            return ToolResult(
                tool_name="websearch",
                status=ToolStatus.ERROR,
                content=None,
                error="Web search requires aiohttp. Install with: pip install aiohttp",
            )
        except Exception as e:
            return ToolResult(
                tool_name="websearch",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )


class WebFetchTool(BaseTool):
    """Tool for fetching web page content."""
    
    def __init__(self, config: Optional[WebFetchToolConfig] = None):
        self.config = config or WebFetchToolConfig()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="webfetch",
            description="Fetch content from a URL",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to fetch content from",
                    required=True,
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="The format to return the content in (text, markdown, or html)",
                    required=False,
                    enum=["text", "markdown", "html"],
                    default="markdown",
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description=f"Optional timeout in seconds (max {self.config.max_timeout_seconds})",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        url = kwargs.get("url")
        format_type = kwargs.get("format", "markdown")
        timeout_seconds = kwargs.get("timeout", self.config.default_timeout_seconds)
        
        if not url:
            return ToolResult(
                tool_name="webfetch",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: url",
            )
        
        # Validate URL
        if not url.startswith("http://") and not url.startswith("https://"):
            return ToolResult(
                tool_name="webfetch",
                status=ToolStatus.ERROR,
                content=None,
                error="URL must start with http:// or https://",
            )
        
        try:
            # Request permission
            await ctx.ask(
                permission="webfetch",
                patterns=[url],
                always=["*"],
                metadata={
                    "url": url,
                    "format": format_type,
                    "timeout": timeout_seconds,
                },
            )
            
            # Limit timeout
            timeout = min(timeout_seconds * 1000, self.config.max_timeout_seconds * 1000) / 1000
            
            # Build headers
            accept_header = self._build_accept_header(format_type)
            headers = {
                "User-Agent": self.config.user_agent,
                "Accept": accept_header,
                "Accept-Language": "en-US,en;q=0.9",
            }
            
            # Fetch URL
            async with asyncio.timeout(timeout):
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        # Handle Cloudflare bot detection
                        if response.status == 403 and response.headers.get("cf-mitigated") == "challenge":
                            headers["User-Agent"] = "opencode"
                            async with session.get(url, headers=headers) as response:
                                pass
                        
                        if not response.ok:
                            raise RuntimeError(f"Request failed with status code: {response.status}")
                        
                        # Check content length
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > self.config.max_response_size:
                            raise RuntimeError("Response too large (exceeds 5MB limit)")
                        
                        content_bytes = await response.read()
                        
                        if len(content_bytes) > self.config.max_response_size:
                            raise RuntimeError("Response too large (exceeds 5MB limit)")
                        
                        content_type = response.headers.get("content-type", "")
                        mime_type = content_type.split(";")[0].strip().lower()
                        
                        title = f"{url} ({content_type})"
                        
                        # Handle images
                        is_image = mime_type.startswith("image/") and mime_type not in [
                            "image/svg+xml", "image/vnd.fastbidsheet"
                        ]
                        
                        if is_image:
                            import base64
                            base64_content = base64.b64encode(content_bytes).decode('utf-8')
                            return ToolResult(
                                tool_name="webfetch",
                                status=ToolStatus.SUCCESS,
                                content="Image fetched successfully",
                                title=title,
                                metadata={},
                                attachments=[{
                                    "type": "file",
                                    "mime": mime_type,
                                    "url": f"data:{mime_type};base64,{base64_content}",
                                }],
                            )
                        
                        # Decode content
                        content = content_bytes.decode('utf-8', errors='replace')
                        
                        # Process based on format
                        output = self._process_content(content, content_type, format_type)
                        
                        return ToolResult(
                            tool_name="webfetch",
                            status=ToolStatus.SUCCESS,
                            content=output,
                            title=title,
                            metadata={},
                        )
        
        except asyncio.TimeoutError:
            return ToolResult(
                tool_name="webfetch",
                status=ToolStatus.ERROR,
                content=None,
                error="Request timed out",
            )
        except ImportError:
            return ToolResult(
                tool_name="webfetch",
                status=ToolStatus.ERROR,
                content=None,
                error="Web fetch requires aiohttp. Install with: pip install aiohttp",
            )
        except Exception as e:
            return ToolResult(
                tool_name="webfetch",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _build_accept_header(self, format_type: str) -> str:
        """Build Accept header based on requested format."""
        headers = {
            "markdown": "text/markdown;q=1.0, text/x-markdown;q=0.9, text/plain;q=0.8, text/html;q=0.7, */*;q=0.1",
            "text": "text/plain;q=1.0, text/markdown;q=0.9, text/html;q=0.8, */*;q=0.1",
            "html": "text/html;q=1.0, application/xhtml+xml;q=0.9, text/plain;q=0.8, text/markdown;q=0.7, */*;q=0.1",
        }
        return headers.get(format_type, "*/*")
    
    def _process_content(self, content: str, content_type: str, format_type: str) -> str:
        """Process content based on requested format."""
        if format_type == "html":
            return content
        
        if "text/html" in content_type:
            if format_type == "markdown":
                return self._html_to_markdown(content)
            elif format_type == "text":
                return self._html_to_text(content)
        
        return content
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown."""
        try:
            import markdownify
            return markdownify.markdownify(html, heading_style="ATX", bullets="-")
        except ImportError:
            # Fallback: basic conversion
            return self._basic_html_to_markdown(html)
    
    def _basic_html_to_markdown(self, html: str) -> str:
        """Basic HTML to Markdown conversion."""
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert headings
        for i in range(6, 0, -1):
            html = re.sub(f'<h{i}[^>]*>(.*?)</h{i}>', f'{"#" * i} \\1\n\n', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Convert bold and italic
        html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Convert links
        html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Convert lists
        html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Convert code
        html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove remaining tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Clean up whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        
        return html.strip()
    
    def _html_to_text(self, html: str) -> str:
        """Extract text from HTML."""
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Add newlines for block elements
        html = re.sub(r'</(?:p|div|br|hr|li|tr|table|h[1-6])>', '\n', html, flags=re.IGNORECASE)
        
        # Remove all tags
        text = re.sub(r'<[^>]+>', '', html)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
