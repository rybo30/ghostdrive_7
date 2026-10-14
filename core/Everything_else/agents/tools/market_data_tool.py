# [market_data_tool.py]

import re
import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "market_data_tool",
    "description": "Retrieves real-time stock quotes, major index performance (S&P 500, NASDAQ, Dow Jones), daily top gainers/losers, and trending market news with direct links.",
    "parameters": {
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "(Optional) List of explicit stock ticker symbols to fetch (e.g., ['AAPL', 'TSLA', 'NVDA']). Defaults to major index summary if omitted."
            },
            "include_movers": {
                "type": "boolean",
                "description": "Whether to fetch today's top gainers and losers. Default is true."
            },
            "include_news": {
                "type": "boolean",
                "description": "Whether to fetch current top market news headlines and links. Default is true."
            }
        },
        "required": []
    }
}

def _fetch_json(url: str) -> Dict[str, Any]:
    """Helper to fetch and parse JSON with standard Browser User-Agent headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _get_single_quote(symbol: str) -> Dict[str, Any]:
    """Retrieves price and percentage change using the reliable v8 chart endpoint."""
    encoded_symbol = urllib.parse.quote(symbol.upper().strip())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?interval=1m&range=1d"
    
    try:
        data = _fetch_json(url)
        chart_result = data.get("chart", {}).get("result", [])
        if not chart_result:
            return {"error": f"Symbol '{symbol}' not found."}
            
        meta = chart_result[0].get("meta", {})
        price = meta.get("regularMarketPrice", 0.0)
        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
        
        change_amt = price - prev_close
        change_pct = (change_amt / prev_close * 100.0) if prev_close else 0.0
        short_name = meta.get("shortName", meta.get("symbol", symbol))

        return {
            "symbol": symbol.upper(),
            "name": short_name,
            "price": price,
            "change_amount": change_amt,
            "change_percent": change_pct
        }
    except Exception as e:
        return {"error": f"Failed fetching {symbol}: {str(e)}"}

def _get_quote_summary(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetches quote summaries for multiple symbols."""
    quotes = []
    for sym in symbols:
        quotes.append(_get_single_quote(sym))
    return quotes

def _get_market_news() -> List[Dict[str, str]]:
    """Fetches trending stock market headlines and URLs using DuckDuckGo Lite."""
    query = "stock market news today"
    encoded_query = urllib.parse.quote(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    news_items = []
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as response:
            html_content = response.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html_content, "html.parser")

            rows = soup.find_all("tr")
            i = 0
            while i < len(rows) and len(news_items) < 5:
                row = rows[i]
                link_elem = row.find("a", class_="result-link")
                if link_elem:
                    title = link_elem.get_text(strip=True)
                    raw_link = link_elem.get("href", "")

                    if "uddg=" in raw_link:
                        match = re.search(r"uddg=([^&]+)", raw_link)
                        if match:
                            raw_link = urllib.parse.unquote(match.group(1))

                    if title and raw_link and raw_link != "N/A":
                        news_items.append({"title": title, "url": raw_link})
                i += 1
    except Exception as e:
        print(f"[market_data_tool] News search error: {e}")

    return news_items

def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    user_tickers = kwargs.get("tickers", [])
    include_movers = kwargs.get("include_movers", True)
    include_news = kwargs.get("include_news", True)

    report = ["=== REAL-TIME FINANCIAL MARKET REPORT ==="]

    # 1. Custom Tickers OR Default Major Indexes
    if user_tickers and isinstance(user_tickers, list) and len(user_tickers) > 0:
        report.append("\n--- REQUESTED TICKER QUOTES ---")
        quotes = _get_quote_summary([t.upper().strip() for t in user_tickers])
        for q in quotes:
            if "error" in q:
                report.append(f"• {q['error']}")
            else:
                sign = "+" if q["change_percent"] >= 0 else ""
                report.append(f"• {q['name']} ({q['symbol']}): ${q['price']:.2f} | {sign}{q['change_percent']:.2f}% ({sign}${q['change_amount']:.2f})")
    else:
        report.append("\n--- MAJOR INDEXES PERFORMANCE ---")
        indexes = ["^GSPC", "^IXIC", "^DJI"]
        quotes = _get_quote_summary(indexes)
        index_names = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones"}
        
        for q in quotes:
            if "error" in q:
                report.append(f"• {q['error']}")
            else:
                sign = "+" if q["change_percent"] >= 0 else ""
                name = index_names.get(q["symbol"], q["name"])
                report.append(f"• {name}: ${q['price']:,.2f} | {sign}{q['change_percent']:.2f}% ({sign}${q['change_amount']:.2f})")

    # 2. Key Stock Movers
    if include_movers:
        report.append("\n--- TODAY'S BIGGEST MOVERS ---")
        movers_watchlist = ["NVDA", "TSLA", "AMD", "AAPL", "AMZN", "MSFT", "GOOGL", "META", "NFLX", "PLTR"]
        mover_quotes = _get_quote_summary(movers_watchlist)
        valid_quotes = [q for q in mover_quotes if "change_percent" in q]
        
        if valid_quotes:
            sorted_movers = sorted(valid_quotes, key=lambda x: x["change_percent"], reverse=True)
            top_gainer = sorted_movers[0]
            top_loser = sorted_movers[-1]
            
            g_sign = "+" if top_gainer["change_percent"] >= 0 else ""
            l_sign = "+" if top_loser["change_percent"] >= 0 else ""
            
            report.append(f"• Top Gainer: {top_gainer['symbol']} ({top_gainer['name']}) -> {g_sign}{top_gainer['change_percent']:.2f}% (${top_gainer['price']:.2f})")
            report.append(f"• Top Loser:  {top_loser['symbol']} ({top_loser['name']}) -> {l_sign}{top_loser['change_percent']:.2f}% (${top_loser['price']:.2f})")

    # 3. Market Headlines & URLs
    if include_news:
        report.append("\n--- TOP MARKET HEADLINES ---")
        news_items = _get_market_news()
        if news_items:
            for item in news_items:
                report.append(f"• {item['title']}")
                report.append(f"  URL: {item['url']}")
        else:
            report.append("• Market news feed unavailable, use index and mover results to analyze the market.")

    report.append("\n=========================================")
    return "\n".join(report)