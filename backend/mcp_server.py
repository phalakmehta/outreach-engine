"""
Block 1: MCP Server
Exposes two tools to the CrewAI agents:
  - web_search: DuckDuckGo text search (free, no key)
  - read_page:  Jina AI Reader — converts any URL to clean markdown (free, no key)
"""
from mcp.server.fastmcp import FastMCP
import urllib.request
import urllib.parse
import json

mcp = FastMCP("outreach-tools")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo. Returns titles, URLs, and snippets."""
    from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
    return "\n---\n".join(results) if results else "No results found."


@mcp.tool()
def read_page(url: str) -> str:
    """Fetch a webpage and return its content as clean markdown using Jina AI Reader."""
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(
        jina_url,
        headers={"Accept": "text/plain", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")[:8000]  # cap at 8k chars to keep context tight
    except Exception as e:
        return f"Error reading {url}: {e}"


if __name__ == "__main__":
    mcp.run()
