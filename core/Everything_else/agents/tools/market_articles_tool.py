# [market_articles_tool.py]

import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "market_articles_tool",
    "description": "Searches for and retrieves deep-linked financial news articles and market trend reports based on specific user instructions, automatically filtering out generic landing pages.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The specific market trend, economic shift, or financial topic to search for (e.g., 'semiconductor market trends', 'interest rate impact on housing', 'AI hardware demand')."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of specific articles to return (default: 5, max: 10)."
            }
        },
        "required": ["topic"]
    }
}


def execute(**kwargs) -> str:
    """Searches for targeted financial articles and extracts clean summaries and links."""
    topic = str(kwargs.get("topic", kwargs.get("query", "market trends"))).strip()
    try:
        max_results = min(max(1, int(kwargs.get("max_results", 5))), 10)
    except Exception:
        max_results = 5

    # Craft query to specifically target insightful financial reporting rather than domain roots
    search_query = f"{topic} financial news report analysis article"
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    articles = []
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html_content, "html.parser")

            rows = soup.find_all("tr")
            i = 0
            while i < len(rows) and len(articles) < max_results:
                row = rows[i]
                link_elem = row.find("a", class_="result-link")
                if link_elem:
                    title = link_elem.get_text(strip=True)
                    raw_link = link_elem.get("href", "")

                    if "uddg=" in raw_link:
                        match = re.search(r"uddg=([^&]+)", raw_link)
                        if match:
                            raw_link = urllib.parse.unquote(match.group(1))

                    # Filter out generic landing pages / domain roots
                    parsed_url = urllib.parse.urlparse(raw_link)
                    path = parsed_url.path.strip("/")
                    is_landing_page = not path or path in ["news", "markets", "stocks", "finance", "investing", "index"]

                    if title and raw_link and not is_landing_page:
                        snippet = "No summary snippet available."
                        if i + 1 < len(rows):
                            snippet_row = rows[i + 1]
                            snippet_elem = snippet_row.find("td", class_="result-snippet")
                            if snippet_elem:
                                snippet = snippet_elem.get_text(strip=True)

                        articles.append({
                            "title": title,
                            "url": raw_link,
                            "snippet": snippet
                        })
                i += 1
    except Exception as e:
        return f"Error fetching market articles: {str(e)}"

    if not articles:
        return f"No specific financial articles found for topic: '{topic}'."

    report = [f"=== FINANCIAL ARTICLES & TREND DIGEST: '{topic.upper()}' ==="]
    for idx, art in enumerate(articles, start=1):
        report.append(f"\n[{idx}] {art['title']}")
        report.append(f"    URL: {art['url']}")
        report.append(f"    Summary: {art['snippet']}")

    report.append("\n=======================================================")
    return "\n".join(report)