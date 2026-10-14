# [media_digest_tool.py]

import json
import re
import socket
import urllib.request
import urllib.parse
from typing import Dict, Any, List

TOOL_SPEC = {
    "name": "media_digest_tool",
    "description": "Aggregates top, viral, and unfiltered discussions across public developer & media platforms (Reddit, Hacker News, Dev.to, Lobsters) without algorithmic bubble tuning.",
    "parameters": {
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "description": "Platform source to query: 'reddit', 'hackernews', 'devto', 'lobsters', or 'all' (default: 'all')."
            },
            "subreddit": {
                "type": "string",
                "description": "(Optional) Target subreddit if platform is 'reddit' (e.g. 'technology', 'all', 'LocalLLaMA'). Defaults to 'all'."
            },
            "max_results": {
                "type": "integer",
                "description": "Number of top viral posts to retrieve per platform (default: 3, max: 5)."
            }
        },
        "required": []
    }
}


def _fetch_reddit_posts(subreddit: str, max_results: int) -> List[Dict[str, str]]:
    """Pulls top trending posts from public Reddit JSON endpoints."""
    clean_sub = re.sub(r"[^a-zA-Z0-9_]", "", subreddit) or "all"
    url = f"https://www.reddit.com/r/{clean_sub}/hot.json?limit={max_results * 2}"
    headers = {"User-Agent": "GhostDriveCompanion/1.0 (Desktop Privacy Node)"}

    results = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            children = data.get("data", {}).get("children", [])

            for item in children:
                post = item.get("data", {})
                if post.get("stickied"):
                    continue

                title = post.get("title", "No Title")
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)
                permalink = f"https://reddit.com{post.get('permalink', '')}"

                results.append({
                    "platform": f"Reddit (r/{clean_sub})",
                    "title": title,
                    "url": permalink,
                    "metrics": f"Upvotes: {score:,} | Comments: {comments:,}"
                })
                if len(results) >= max_results:
                    break
    except Exception as e:
        results.append({
            "platform": "Reddit",
            "title": "Failed to load Reddit digest",
            "url": "N/A",
            "metrics": f"Error: {str(e)}"
        })

    return results


def _fetch_hacker_news_posts(max_results: int) -> List[Dict[str, str]]:
    """Fetches top stories from the official Firebase Hacker News API."""
    results = []
    try:
        top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        req = urllib.request.Request(top_ids_url, headers={"User-Agent": "GhostDriveCompanion/1.0"})
        
        with urllib.request.urlopen(req, timeout=6) as resp:
            story_ids = json.loads(resp.read().decode("utf-8"))[:max_results]

        for s_id in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{s_id}.json"
            item_req = urllib.request.Request(item_url, headers={"User-Agent": "GhostDriveCompanion/1.0"})
            with urllib.request.urlopen(item_req, timeout=5) as item_resp:
                story = json.loads(item_resp.read().decode("utf-8"))
                title = story.get("title", "No Title")
                score = story.get("score", 0)
                comments = story.get("descendants", 0)
                hn_url = story.get("url", f"https://news.ycombinator.com/item?id={s_id}")

                results.append({
                    "platform": "Hacker News",
                    "title": title,
                    "url": hn_url,
                    "metrics": f"Points: {score:,} | Comments: {comments:,}"
                })
    except Exception as e:
        results.append({
            "platform": "Hacker News",
            "title": "Failed to load Hacker News digest",
            "url": "N/A",
            "metrics": f"Error: {str(e)}"
        })

    return results


def _fetch_devto_posts(max_results: int) -> List[Dict[str, str]]:
    """Fetches top trending tech articles from Dev.to public API."""
    url = f"https://dev.to/api/articles?top=1&per_page={max_results}"
    headers = {"User-Agent": "GhostDriveCompanion/1.0"}
    results = []

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            articles = json.loads(resp.read().decode("utf-8"))
            for a in articles[:max_results]:
                title = a.get("title", "No Title")
                reactions = a.get("public_reactions_count", 0)
                comments = a.get("comments_count", 0)
                article_url = a.get("url", "N/A")

                results.append({
                    "platform": "Dev.to",
                    "title": title,
                    "url": article_url,
                    "metrics": f"Reactions: {reactions:,} | Comments: {comments:,}"
                })
    except Exception as e:
        results.append({
            "platform": "Dev.to",
            "title": "Failed to load Dev.to digest",
            "url": "N/A",
            "metrics": f"Error: {str(e)}"
        })

    return results


def _fetch_lobsters_posts(max_results: int) -> List[Dict[str, str]]:
    """Fetches trending technical discussions from Lobsters public JSON API."""
    url = "https://lobste.rs/hottest.json"
    headers = {"User-Agent": "GhostDriveCompanion/1.0"}
    results = []

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            stories = json.loads(resp.read().decode("utf-8"))
            for s in stories[:max_results]:
                title = s.get("title", "No Title")
                score = s.get("score", 0)
                comments = s.get("comment_count", 0)
                story_url = s.get("url") or s.get("comments_url", "N/A")

                results.append({
                    "platform": "Lobsters",
                    "title": title,
                    "url": story_url,
                    "metrics": f"Score: {score:,} | Comments: {comments:,}"
                })
    except Exception as e:
        results.append({
            "platform": "Lobsters",
            "title": "Failed to load Lobsters digest",
            "url": "N/A",
            "metrics": f"Error: {str(e)}"
        })

    return results


def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    socket.setdefaulttimeout(8)

    platform = str(kwargs.get("platform", "all")).lower().strip()
    subreddit = str(kwargs.get("subreddit", "all")).strip()

    try:
        max_results = min(max(1, int(kwargs.get("max_results", 3))), 5)
    except Exception:
        max_results = 3

    digest_entries = []

    if platform in ["reddit", "all"]:
        digest_entries.extend(_fetch_reddit_posts(subreddit, max_results))

    if platform in ["hackernews", "hn", "all"]:
        digest_entries.extend(_fetch_hacker_news_posts(max_results))

    if platform in ["devto", "dev.to", "all"]:
        digest_entries.extend(_fetch_devto_posts(max_results))

    if platform in ["lobsters", "all"]:
        digest_entries.extend(_fetch_lobsters_posts(max_results))

    report = ["=== UNFILTERED CROSS-PLATFORM MEDIA DIGEST ==="]

    if not digest_entries:
        report.append("No media entries could be fetched at this time.")
    else:
        for idx, entry in enumerate(digest_entries, start=1):
            report.append(f"\n[{idx}] [{entry['platform']}] {entry['title']}")
            report.append(f"    URL: {entry['url']}")
            report.append(f"    Engagement: {entry['metrics']}")

    report.append("\n=============================================")
    return "\n".join(report)