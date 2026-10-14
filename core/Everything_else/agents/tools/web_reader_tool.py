import re
import socket
import urllib.request
from bs4 import BeautifulSoup
from typing import Dict, Any

TOOL_SPEC = {
    "name": "web_reader_tool",
    "description": "Fetches a webpage URL, strips HTML tags/scripts, and extracts the main readable text content.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP or HTTPS URL of the webpage to scrape and read."
            },
            "max_characters": {
                "type": "integer",
                "description": "Maximum character limit for the extracted content (default 4000)."
            }
        },
        "required": ["url"]
    }
}

def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    # Enforce hard socket timeout
    socket.setdefaulttimeout(8)

    raw_url = kwargs.get("url", "")
    if isinstance(raw_url, dict):
        raw_url = raw_url.get("url", raw_url.get("value", ""))
    
    url = str(raw_url).strip()
    max_chars = kwargs.get("max_characters", 4000)

    if not url:
        return "Error: 'url' parameter is required."

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")

        # Strip out non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            element.decompose()

        # Extract remaining text
        text = soup.get_text(separator=" ")
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = "\n".join(chunk for chunk in chunks if chunk)

        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "\n...[Content Truncated]"

        return f"=== WEBPAGE CONTENT ({url}) ===\n{clean_text}"

    except Exception as e:
        return f"Web Reader Error for '{url}': {str(e)}"