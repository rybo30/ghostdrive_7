# [sports_news_tool.py]

import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "sports_news_tool",
    "description": "Retrieves real-time sports news, trade updates, roster moves, and upcoming game info across professional and college leagues (NFL, NBA, MLB, NHL, NCAAF, NCAAB).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(Optional) Specific player name, college/pro team, or search query (e.g., 'Michigan Wolverines football', 'Kawhi Leonard trade news'). Defaults to broad top sports headlines if omitted."
            },
            "league": {
                "type": "string",
                "enum": ["all", "nfl", "nba", "mlb", "nhl", "ncaaf", "ncaab"],
                "description": "Filter by league. Default is 'all'."
            }
        },
        "required": []
    }
}

def _fetch_rss_feed(url: str, max_items: int = 4) -> List[Dict[str, str]]:
    """Helper function to fetch and extract titles and links from RSS feeds."""
    headers = {"User-Agent": "Mozilla/5.0"}
    items = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_data = resp.read().decode("utf-8", errors="ignore")
            
            raw_items = re.findall(r"<item>(.*?)</item>", xml_data, re.DOTALL)
            for raw in raw_items[:max_items]:
                title_match = re.search(r"<title>(.*?)</title>", raw, re.DOTALL)
                link_match = re.search(r"<link>(.*?)</link>", raw, re.DOTALL)
                
                title = title_match.group(1).strip() if title_match else ""
                title = title.replace("<![CDATA[", "").replace("]]>", "").strip()
                
                link = link_match.group(1).strip() if link_match else ""
                link = link.replace("<![CDATA[", "").replace("]]>", "").strip()

                if title:
                    items.append({"title": title, "link": link})
    except Exception as e:
        items.append({"title": f"Feed error: {str(e)}", "link": ""})
    return items

def _search_duckduckgo_sports(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Performs targeted web query when specific sports questions are asked."""
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = urllib.parse.urlencode({"q": f"{query} sports news"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    results = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            matches = re.findall(r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html)

            for idx, (link, title) in enumerate(matches[:max_results]):
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                clean_snippet = re.sub(r'<[^>]+>', '', snippets[idx]).strip() if idx < len(snippets) else "No summary."
                
                if "uddg=" in link:
                    match = re.search(r"uddg=([^&]+)", link)
                    if match:
                        link = urllib.parse.unquote(match.group(1))

                results.append({"title": clean_title, "snippet": clean_snippet, "link": link})
    except Exception as e:
        results.append({"title": "Search Error", "snippet": str(e), "link": ""})
    return results

def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    query = kwargs.get("query", "").strip()
    league = kwargs.get("league", "all").strip().lower()

    report = ["=== REAL-TIME SPORTS HEADLINES & UPDATES ==="]

    if query:
        report.append(f"\n--- TARGETED QUERY RESULT: '{query}' ---")
        search_results = _search_duckduckgo_sports(query)
        for r in search_results:
            report.append(f"• {r['title']}")
            if r.get('snippet'):
                report.append(f"  Summary: {r['snippet']}")
            if r.get('link'):
                report.append(f"  Link: {r['link']}\n")
        report.append("=========================================")
        return "\n".join(report)

    if league in ["all", "nfl"]:
        report.append("\n--- TOP NFL HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/nfl/news", max_items=3):
            report.append(f"• {item['title']}")

    if league in ["all", "nba"]:
        report.append("\n--- TOP NBA HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/nba/news", max_items=3):
            report.append(f"• {item['title']}")

    if league in ["all", "ncaaf"]:
        report.append("\n--- TOP COLLEGE FOOTBALL (NCAAF) HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/college-football/news", max_items=3):
            report.append(f"• {item['title']}")

    if league in ["all", "ncaab"]:
        report.append("\n--- TOP COLLEGE BASKETBALL (NCAAB) HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/mens-college-basketball/news", max_items=3):
            report.append(f"• {item['title']}")

    if league == "mlb":
        report.append("\n--- TOP MLB HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/mlb/news", max_items=3):
            report.append(f"• {item['title']}")

    if league == "nhl":
        report.append("\n--- TOP NHL HEADLINES ---")
        for item in _fetch_rss_feed("https://www.espn.com/espn/rss/nhl/news", max_items=3):
            report.append(f"• {item['title']}")

    report.append("\n=========================================")
    return "\n".join(report)