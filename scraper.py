"""
BBC Visual Journalism scrollytelling tracker — scraper.
Reads seeds.txt, fetches each idt- article, extracts metadata,
follows cross-links to discover new articles, and writes data/articles.json.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SEEDS_FILE = "seeds.txt"
BLOCKLIST_FILE = "blocklist.txt"
DATA_FILE = "data/articles.json"
IDT_PATTERN = re.compile(r"idt-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
BBC_BASE = "https://www.bbc.co.uk"
CDX_API = "http://web.archive.org/cdx/search/cdx"
SLEEP_SECONDS = 2
PUBLISHED_AFTER = datetime(2024, 11, 6, tzinfo=timezone.utc)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


def format_date(iso_string):
    if not iso_string:
        return "–"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%-d %b %Y")
    except ValueError:
        return iso_string[:10]


def write_summary(new_articles, all_articles):
    run_date = datetime.now(timezone.utc).strftime("%-d %b %Y")
    n = len(new_articles)
    if n:
        subject = f"BBC Scrolly Tracker — {n} new article{'s' if n != 1 else ''} ({run_date})"
    else:
        subject = f"BBC Scrolly Tracker — no new articles ({run_date})"

    lines = [subject, "=" * len(subject), ""]
    if new_articles:
        lines.append(f"{n} new article{'s' if n != 1 else ''} added:\n")
        for a in sorted(new_articles, key=lambda x: x.get("published_date") or "", reverse=True):
            lines.append(f"• {a['title']} ({format_date(a.get('published_date'))})")
            if a.get("topics"):
                lines.append(f"  Topics:     {', '.join(a['topics'])}")
            if a.get("components"):
                lines.append(f"  Components: {', '.join(a['components'])}")
            lines.append("")
    else:
        lines += ["No new articles were found this week.", ""]

    lines += ["-" * 40, f"Total in tracker: {len(all_articles)} articles"]

    with open("scraper_summary.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    with open("scraper_subject.txt", "w") as f:
        f.write(subject)


def load_blocklist():
    if not os.path.exists(BLOCKLIST_FILE):
        return set()
    with open(BLOCKLIST_FILE) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return set(lines)


def load_seeds():
    if not os.path.exists(SEEDS_FILE):
        return []
    with open(SEEDS_FILE) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return [l for l in lines if "idt-" in l]


def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_data(articles):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def fetch(url):
    time.sleep(SLEEP_SECONDS)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  [error] {e}")
        return None


def extract_idt_ids(html):
    """Return all idt- UUID strings found anywhere in the page HTML."""
    return set(IDT_PATTERN.findall(html))


def extract_metadata(url, html):
    soup = BeautifulSoup(html, "lxml")

    def meta(prop=None, name=None):
        if prop:
            tag = soup.find("meta", property=prop)
        else:
            tag = soup.find("meta", attrs={"name": name})
        return (tag.get("content") or "").strip() if tag else None

    title = (
        meta(prop="og:title")
        or (soup.find("h1").get_text(strip=True) if soup.find("h1") else None)
        or (soup.find("title").get_text(strip=True) if soup.find("title") else None)
    )
    # Strip trailing " - BBC News" suffix
    if title and title.endswith(" - BBC News"):
        title = title[: -len(" - BBC News")]

    subtitle = meta(prop="og:description") or meta(name="description")

    topic = meta(prop="og:article:section") or meta(name="article:section")

    # Published date from JSON-LD first, then meta tags
    published_date = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    published_date = item.get("datePublished") or item.get("dateCreated")
                    if published_date:
                        break
        except (json.JSONDecodeError, TypeError):
            pass
        if published_date:
            break

    if not published_date:
        published_date = (
            meta(prop="article:published_time")
            or meta(name="article:published_time")
            or meta(name="DC.date")
        )

    # Last resort: parse a visible date like "17 January 2025" from page text
    if not published_date:
        date_match = re.search(
            r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(202\d)\b',
            soup.get_text()
        )
        if date_match:
            try:
                published_date = datetime.strptime(date_match.group(), "%d %B %Y").replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

    # Thumbnail from og:image
    og_image = soup.find("meta", property="og:image")
    thumbnail = (og_image.get("content") or "").strip() if og_image else None

    # Byline — scan visible text lines for the attribution string
    byline = None
    page_text = soup.get_text(separator="\n")
    for line in page_text.splitlines():
        line = line.strip()
        if line.lower().startswith("by ") and len(line) < 120:
            byline = line
            break

    # Fallback: dedicated byline element used on some idt- pages
    if not byline:
        el = soup.find(class_="sm-article-info__byline-author")
        if el:
            byline = el.get_text(strip=True)

    article = {
        "url": url,
        "title": title,
        "subtitle": subtitle,
        "published_date": published_date,
        "thumbnail": thumbnail,
        "byline": byline,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }
    article["topics"] = classify_topics(article)
    article["components"] = detect_components(html)
    return article


def classify_topics(article):
    title = (article.get("title") or "").lower()
    subtitle = (article.get("subtitle") or "").lower()
    text = f"{title} {subtitle}"
    topics = set()

    if any(p in title for p in ["in pictures", "extraordinary photos", "life in pictures"]):
        topics.add("In pictures")

    if any(p in text for p in ["artemis", "moon mission", "dinosaur", "human-made fire"]):
        topics.add("Science")

    if any(p in text for p in ["snore", "breathing", "sleep apnea", "pandemic", "covid"]):
        topics.add("Health")

    if any(p in text for p in ["oscars", "taylor swift", "armani", "showgirl", "gig ticket", "fashion"]):
        topics.add("Culture")

    if any(p in text for p in ["cost you more", "rare earths", "green superpower", "gig ticket"]):
        topics.add("Business")

    if any(p in text for p in ["letby", "uk visit", "our sea beds", "letter from the king"]):
        topics.add("UK")

    world_signals = [
        "iran", "gaza", "trump", "china", "russia", "putin", "pope", "glacier",
        "earthquake", "wildfire", "louvre", "hong kong", "myanmar", "war", "protest",
        "military", "nuclear", "arctic", "ukraine", "ceasefire", "white house",
        "inauguration", "election", "israel", "hostage",
    ]
    if any(k in text for k in world_signals):
        topics.add("World")

    # In pictures always needs a substantive partner
    if topics == {"In pictures"} or not topics:
        topics.add("World")

    return sorted(topics)


def detect_components(html):
    components = []
    if "Immersive" in html:
        components.append("3D")
    if "scrolly-video" in html:
        components.append("Scrollable video")
    if "sm-video-autoplay" in html:
        components.append("Autoplay video")
    return components


def is_visual_journalism(article):
    byline = (article.get("byline") or "").lower()
    return "visual journalism" in byline or "visual and data journalism" in byline


def is_after_cutoff(article):
    raw = article.get("published_date") or ""
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt >= PUBLISHED_AFTER
    except ValueError:
        return False


def fetch_cdx_urls():
    """Query Wayback Machine CDX API for BBC idt- URLs archived since the cutoff date."""
    print("Querying Wayback Machine CDX API…")
    params = {
        "url": "bbc.co.uk/news/resources/idt-*",
        "output": "json",
        "fl": "original",
        "collapse": "urlkey",
        "from": PUBLISHED_AFTER.strftime("%Y%m%d"),
        "limit": 5000,
    }
    try:
        resp = requests.get(CDX_API, params=params, timeout=30)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        print(f"  [CDX error] {e}")
        return []

    if not rows or len(rows) < 2:
        return []

    seen = set()
    urls = []
    for row in rows[1:]:  # first row is the header
        raw = row[0]
        url = "https://" + raw.split("://", 1)[-1].split("?")[0].split("#")[0]
        url = url.replace("https://bbc.co.uk/", "https://www.bbc.co.uk/")
        if "bbc.co.uk/news/resources/idt-" in url and url not in seen:
            seen.add(url)
            urls.append(url)

    print(f"  CDX returned {len(urls)} idt- URLs")
    return urls


def main():
    seeds = load_seeds()
    cdx_urls = fetch_cdx_urls()
    blocklist = load_blocklist()
    existing = load_existing()
    # Only pre-load confirmed VJ articles within the date window
    articles_by_url = {a["url"]: a for a in existing if is_visual_journalism(a) and is_after_cutoff(a)}
    existing_urls = set(articles_by_url.keys())

    # BFS queue: CDX urls + seeds + previously confirmed VJ URLs (to re-check for new cross-links)
    queue = list(dict.fromkeys([*cdx_urls, *seeds, *articles_by_url.keys()]))
    visited = set(articles_by_url.keys())  # URLs whose HTML we've already parsed
    scrape_count = 0

    print(f"CDX: {len(cdx_urls)}  |  Seeds: {len(seeds)}  |  Blocklist: {len(blocklist)}  |  Already in data (VJ): {len(articles_by_url)}")

    while queue:
        url = queue.pop(0)

        if url in visited or url in blocklist:
            continue
        visited.add(url)

        print(f"\nScraping: {url}")
        resp = fetch(url)
        if not resp:
            continue

        html = resp.text

        # Discover cross-linked idt- articles and add unseen ones to the queue
        for idt_id in extract_idt_ids(html):
            candidate = f"{BBC_BASE}/news/resources/{idt_id}"
            if candidate not in visited and candidate not in queue:
                print(f"  + discovered: {candidate}")
                queue.append(candidate)

        article = extract_metadata(url, html)
        scrape_count += 1

        if is_visual_journalism(article) and is_after_cutoff(article):
            articles_by_url[url] = article
            print(f"  [VJ] title: {article['title']}")
            print(f"       date:  {article['published_date']}")
            print(f"       byline: {article['byline']}")
        elif is_visual_journalism(article):
            print(f"  [old] before cutoff ({(article['published_date'] or '')[:10]}) — {article['title']}")
        else:
            print(f"  [skip] not Visual Journalism — byline: {article['byline']!r}")

    vj_articles = sorted(
        articles_by_url.values(),
        key=lambda a: a.get("published_date") or "",
        reverse=True,
    )
    new_articles = [a for a in vj_articles if a["url"] not in existing_urls]
    save_data(vj_articles)
    write_summary(new_articles, vj_articles)
    print(f"\nDone. {len(vj_articles)} VJ articles saved ({len(new_articles)} new).")
    print(f"  ({scrape_count} pages fetched this run)")


if __name__ == "__main__":
    main()
