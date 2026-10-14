import re
import socket
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "web_search_tool",
    "description": "Performs web searches using a privacy-focused search engine. Supports up to 3 iterative search queries in a single execution to refine and aggregate results.",
    "parameters": {
        "type": "object",
        "properties": {
            "query_1": {
                "type": "string",
                "description": "The primary search query to execute (Attempt 1)."
            },
            "query_2": {
                "type": "string",
                "description": "(Optional) A secondary search query to refine results if the first query is too broad or narrow (Attempt 2)."
            },
            "query_3": {
                "type": "string",
                "description": "(Optional) A third search query for deeper investigation (Attempt 3)."
            },
            "max_results_per_query": {
                "type": "integer",
                "description": "Number of top results to extract per search attempt (default is 5, max 10)."
            }
        },
        "required": ["query_1"]
    }
}


def _execute_single_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Performs a GET request to DuckDuckGo Lite and parses titles, links, and snippets."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    results = []

    try:
        # Enforce strict 6-second timeout on the HTTP connection
        with urllib.request.urlopen(req, timeout=6) as response:
            html_content = response.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html_content, "html.parser")

            # DuckDuckGo Lite formats search results in table rows (tr)
            rows = soup.find_all("tr")
            i = 0
            while i < len(rows) and len(results) < max_results:
                row = rows[i]
                link_elem = row.find("a", class_="result-link")
                if link_elem:
                    title = link_elem.get_text(strip=True)
                    raw_link = link_elem.get("href", "")

                    if "uddg=" in raw_link:
                        match = re.search(r"uddg=([^&]+)", raw_link)
                        if match:
                            raw_link = urllib.parse.unquote(match.group(1))

                    snippet = "No snippet available."
                    if i + 1 < len(rows):
                        snippet_elem = rows[i + 1].find("td", class_="result-snippet")
                        if snippet_elem:
                            snippet = snippet_elem.get_text(strip=True)

                    results.append({
                        "title": title,
                        "url": raw_link,
                        "snippet": snippet
                    })
                i += 1

    except Exception as e:
        results.append({
            "title": "Search Request Error",
            "url": "N/A",
            "snippet": f"Failed web search for '{query}': {str(e)}"
        })

    return results


def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    # Force default socket timeout to prevent daemon hanging
    socket.setdefaulttimeout(8)

    # Sanitize and force string conversion on inputs
    q1_raw = kwargs.get("query_1", kwargs.get("query", ""))
    q2_raw = kwargs.get("query_2", "")
    q3_raw = kwargs.get("query_3", "")

    # If LLM passed a dict schema hallucination, unwrap it to a string
    def _to_clean_str(val: Any) -> str:
        if isinstance(val, dict):
            return str(val.get("query_1", val.get("query", val.get("value", "")))).strip()
        return str(val).strip()

    query_1 = _to_clean_str(q1_raw)
    query_2 = _to_clean_str(q2_raw)
    query_3 = _to_clean_str(q3_raw)

    max_results = kwargs.get("max_results_per_query", 5)
    try:
        max_results = min(max(1, int(max_results)), 10)
    except Exception:
        max_results = 5

    if not query_1:
        return "Error: 'query_1' parameter is required to execute a web search."

    search_queries = [q for q in [query_1, query_2, query_3] if q][:3]

    output_report = []
    output_report.append(f"=== WEB SEARCH LOG ({len(search_queries)} Attempt(s) Executed) ===")

    for idx, query in enumerate(search_queries, start=1):
        output_report.append(f"\n--- ATTEMPT {idx}: '{query}' ---")
        results = _execute_single_search(query, max_results)

        if not results:
            output_report.append("No relevant web results were found for this query.")
            continue

        for r_idx, res in enumerate(results, start=1):
            output_report.append(f"[{r_idx}] {res['title']}")
            output_report.append(f"    URL: {res['url']}")
            output_report.append(f"    Snippet: {res['snippet']}\n")

    output_report.append("=== END OF SEARCH LOG ===")
    return "\n".join(output_report)