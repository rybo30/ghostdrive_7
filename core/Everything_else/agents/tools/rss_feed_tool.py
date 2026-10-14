# [rss_feed_tool.py]

import re
import socket
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "rss_feed_tool",
    "description": "Fetches and parses headlines, published dates, summaries, and URLs from any public RSS or Atom news feed.",
    "parameters": {
        "type": "object",
        "properties": {
            "feed_url": {
                "type": "string",
                "description": "The direct URL of the RSS or Atom XML feed to parse (e.g., 'https://news.ycombinator.com/rss' or 'https://feeds.bbci.co.uk/news/rss.xml')."
            },
            "max_items": {
                "type": "integer",
                "description": "Maximum number of feed entries to return (default: 5, max: 10)."
            }
        },
        "required": ["feed_url"]
    }
}


def _clean_html_tags(raw_html: str) -> str:
    """Strips HTML markup and unescapes text for clean plain-text outputs."""
    if not raw_html:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_html)
    clean_text = re.sub(r"\s+", " ", clean_text)
    return clean_text.strip()


def _parse_xml_feed(xml_data: str, max_items: int) -> List[Dict[str, str]]:
    """Parses standard RSS 2.0 and Atom XML structures into item dicts."""
    items = []
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        return [{"error": f"Failed to parse feed XML structure: {str(e)}"}]

    # Check for RSS 2.0 channel items
    channel = root.find("channel")
    if channel is not None:
        raw_items = channel.findall("item")
        for item in raw_items[:max_items]:
            title = item.findtext("title", "No Title Available").strip()
            link = item.findtext("link", "N/A").strip()
            
            # Prefer description or pubDate
            description = item.findtext("description", "No description provided.").strip()
            pub_date = item.findtext("pubDate", "").strip()

            items.append({
                "title": title,
                "url": link,
                "published": pub_date,
                "summary": _clean_html_tags(description)[:250]
            })
        return items

    # Check for Atom feed entries
    # Atom feeds use XML namespaces
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns) or root.findall("entry")

    for entry in entries[:max_items]:
        title_elem = entry.find("atom:title", ns) if entry.find("atom:title", ns) is not None else entry.find("title")
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No Title Available"

        # Atom links can be attributes: <link href="..."/>
        link = "N/A"
        link_elem = entry.find("atom:link", ns) if entry.find("atom:link", ns) is not None else entry.find("link")
        if link_elem is not None:
            link = link_elem.attrib.get("href", link_elem.text or "N/A")

        summary_elem = entry.find("atom:summary", ns) if entry.find("atom:summary", ns) is not None else entry.find("summary")
        summary_text = summary_elem.text if summary_elem is not None and summary_elem.text else "No summary provided."

        published_elem = entry.find("atom:updated", ns) if entry.find("atom:updated", ns) is not None else entry.find("updated")
        pub_date = published_elem.text if published_elem is not None and published_elem.text else ""

        items.append({
            "title": title,
            "url": link,
            "published": pub_date,
            "summary": _clean_html_tags(summary_text)[:250]
        })

    return items


def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    socket.setdefaulttimeout(8)

    feed_url = str(kwargs.get("feed_url", kwargs.get("url", ""))).strip()
    if not feed_url:
        return "Error: 'feed_url' parameter is required to fetch an RSS feed."

    if not (feed_url.startswith("http://") or feed_url.startswith("https://")):
        feed_url = "https://" + feed_url

    try:
        max_items = min(max(1, int(kwargs.get("max_items", 5))), 10)
    except Exception:
        max_items = 5

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*"
    }

    report = [f"=== RSS FEED DIGEST ({feed_url}) ==="]

    try:
        req = urllib.request.Request(feed_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as response:
            raw_xml = response.read().decode("utf-8", errors="ignore")
            feed_items = _parse_xml_feed(raw_xml, max_items)

            if not feed_items:
                return f"No valid feed entries found at {feed_url}."

            if "error" in feed_items[0]:
                return f"RSS Tool Error: {feed_items[0]['error']}"

            for idx, item in enumerate(feed_items, start=1):
                report.append(f"\n[{idx}] {item['title']}")
                if item['published']:
                    report.append(f"    Date: {item['published']}")
                report.append(f"    URL: {item['url']}")
                report.append(f"    Summary: {item['summary']}")

    except Exception as e:
        report.append(f"Error fetching RSS feed: {str(e)}")

    report.append("\n=== END OF FEED DIGEST ===")
    return "\n".join(report)