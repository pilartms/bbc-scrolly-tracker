"""
BBC Visual Journalism scrollytelling tracker — dashboard builder.
Reads data/articles.json and writes docs/index.html.
"""

import json
import os
from datetime import datetime, timezone

DATA_FILE = "data/articles.json"
MANUAL_DATA_FILE = "data/manual_articles.json"
OUTPUT_FILE = "docs/index.html"

TOPIC_COLOURS = {
    "World":       "#1a6496",
    "UK":          "#bb1919",
    "Business":    "#2e7d32",
    "Culture":     "#6a1b9a",
    "Science":     "#00838f",
    "Health":      "#e65100",
    "In pictures": "#546e7a",
}

COMPONENT_COLOURS = {
    "3D":               "#c62828",
    "Scrollable video": "#1565c0",
    "Autoplay video":   "#558b2f",
}


def load_articles():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        articles = json.load(f)
    if os.path.exists(MANUAL_DATA_FILE):
        with open(MANUAL_DATA_FILE) as f:
            manual = json.load(f)
        existing_urls = {a["url"] for a in articles}
        articles += [a for a in manual if a["url"] not in existing_urls]
    return sorted(articles, key=lambda a: a.get("published_date") or "", reverse=True)


def format_byline(raw):
    if not raw:
        return "–"
    stripped = raw.strip()
    if stripped.lower().startswith("by "):
        stripped = stripped[3:].strip()
    if stripped:
        stripped = stripped[0].upper() + stripped[1:]
    return stripped or "–"


def format_date(iso_string):
    if not iso_string:
        return "–"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%-d %b %Y")
    except ValueError:
        return iso_string[:10]


def topic_tags_html(topics):
    tags = []
    for t in topics:
        colour = TOPIC_COLOURS.get(t, "#888")
        tags.append(
            f'<span class="topic-tag" style="background:{colour}">{t}</span>'
        )
    return " ".join(tags)


def component_tags_html(components):
    tags = []
    for c in components:
        colour = COMPONENT_COLOURS.get(c, "#666")
        tags.append(
            f'<span class="component-tag" style="border-color:{colour};color:{colour}">{c}</span>'
        )
    return " ".join(tags)


def build_rows(articles):
    rows = []
    for a in articles:
        url = a.get("url", "")
        title = a.get("title") or "Untitled"
        subtitle = a.get("subtitle") or ""
        date = format_date(a.get("published_date"))
        byline = format_byline(a.get("byline"))
        topics = a.get("topics") or ["World"]
        components = a.get("components") or []
        thumb = a.get("thumbnail") or ""

        thumb_html = (
            f'<a href="{url}" target="_blank" rel="noopener"><img src="{thumb}" alt="" loading="lazy"></a>'
            if thumb
            else '<div class="no-thumb"></div>'
        )

        all_tags = topic_tags_html(topics)
        if components:
            all_tags += " " + component_tags_html(components)

        topics_json = json.dumps(topics)
        components_json = json.dumps(components)

        rows.append(f"""
      <tr data-topics='{topics_json}' data-components='{components_json}'>
        <td class="thumb-cell">{thumb_html}</td>
        <td>
          <a href="{url}" target="_blank" rel="noopener">{title}</a>
          <p class="subtitle">{subtitle}</p>
        </td>
        <td data-date="{a.get('published_date') or ''}">{date}</td>
        <td class="byline-cell">{byline}</td>
        <td class="tags-cell">{all_tags}</td>
      </tr>""")
    return "\n".join(rows)


def render(articles):
    updated = datetime.now(timezone.utc).strftime("%-d %b %Y, %H:%M UTC")
    count = len(articles)
    rows_html = build_rows(articles)

    all_topics = sorted({t for a in articles for t in (a.get("topics") or [])})
    topic_options = "\n".join(
        f'        <option value="{t}">{t}</option>' for t in all_topics
    )

    all_components = sorted({c for a in articles for c in (a.get("components") or [])})
    component_options = "\n".join(
        f'        <option value="{c}">{c}</option>' for c in all_components
    )

    # Date range bounds for the inputs
    dates = sorted(a["published_date"][:10] for a in articles if a.get("published_date"))
    date_min = dates[0] if dates else ""
    date_max = dates[-1] if dates else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBC Scrolly Tracker</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔴</text></svg>">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5;
      color: #111;
      min-height: 100vh;
    }}

    header {{
      background: #bb1919;
      color: #fff;
      padding: 1.25rem 1.5rem;
      display: flex;
      align-items: baseline;
      gap: 1rem;
    }}
    header h1 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.01em; }}
    header .meta {{ font-size: 0.82rem; opacity: 0.8; }}

    .controls {{
      background: #fff;
      border-bottom: 1px solid #e0e0e0;
      padding: 0.75rem 1.5rem;
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: center;
    }}
    .controls input, .controls select {{
      border: 1px solid #ccc;
      border-radius: 4px;
      padding: 0.4rem 0.6rem;
      font-size: 0.875rem;
      outline: none;
    }}
    .controls input[type="search"] {{ flex: 1; min-width: 180px; }}
    .controls input[type="date"] {{ min-width: 130px; }}
    .controls input:focus, .controls select:focus {{ border-color: #bb1919; }}
    .controls .separator {{
      width: 1px;
      height: 1.5rem;
      background: #ddd;
      align-self: center;
    }}
    .controls label {{
      font-size: 0.78rem;
      color: #888;
      white-space: nowrap;
    }}
    .count {{ font-size: 0.82rem; color: #666; margin-left: auto; }}
    .clear-btn {{
      background: none;
      border: 1px solid #ccc;
      border-radius: 4px;
      padding: 0.35rem 0.6rem;
      font-size: 0.8rem;
      color: #666;
      cursor: pointer;
      white-space: nowrap;
    }}
    .clear-btn:hover {{ border-color: #bb1919; color: #bb1919; }}

    main {{ padding: 1.5rem; overflow-x: auto; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border-radius: 6px;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,.08);
      font-size: 0.875rem;
    }}
    thead {{ background: #222; color: #fff; }}
    thead th {{
      padding: 0.75rem 1rem;
      text-align: left;
      font-weight: 600;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }}
    thead th:hover {{ background: #333; }}
    thead th.sorted-asc::after {{ content: " ↑"; }}
    thead th.sorted-desc::after {{ content: " ↓"; }}

    tbody tr {{ border-bottom: 1px solid #f0f0f0; }}
    tbody tr:hover {{ background: #fafafa; }}
    tbody td {{ padding: 0.75rem 1rem; vertical-align: top; }}

    .thumb-cell {{
      width: 175px;
      padding: 0.5rem;
      vertical-align: middle;
      text-align: center;
    }}
    tbody td[data-date] {{ white-space: nowrap; }}
    .thumb-cell img {{ width: 160px; height: 107px; object-fit: cover; border-radius: 3px; display: block; }}
    .thumb-cell .no-thumb {{ width: 160px; height: 107px; background: #e8e8e8; border-radius: 3px; margin: 0 auto; }}

    tbody td a {{ color: #bb1919; text-decoration: none; font-weight: 600; line-height: 1.3; font-size: 0.95rem; }}
    tbody td a:hover {{ text-decoration: underline; }}
    .subtitle {{ color: #555; font-size: 0.82rem; margin-top: 0.2rem; line-height: 1.4; }}

    .topic-tag {{
      display: inline-block;
      border-radius: 3px;
      padding: 0.2rem 0.5rem;
      font-size: 0.75rem;
      font-weight: 600;
      color: #fff;
      margin-right: 0.25rem;
      margin-bottom: 0.2rem;
      white-space: nowrap;
    }}

    .component-tag {{
      display: inline-block;
      border-radius: 3px;
      border: 1.5px solid;
      padding: 0.15rem 0.45rem;
      font-size: 0.75rem;
      font-weight: 600;
      margin-right: 0.25rem;
      margin-bottom: 0.2rem;
      white-space: nowrap;
      background: transparent;
    }}

    .byline-cell {{
      color: #555;
      font-size: 0.82rem;
      width: 160px;
      max-width: 160px;
    }}

    .no-results-msg {{
      text-align: center;
      padding: 2.5rem 1rem !important;
      color: #999;
      font-style: italic;
    }}

    .hidden {{ display: none !important; }}

    footer {{
      text-align: center;
      padding: 1.5rem;
      font-size: 0.78rem;
      color: #999;
    }}

    /* ── Date range group — keeps From/To together on wrap ── */
    .date-range {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-shrink: 0;
    }}
    .date-range label {{ margin: 0; }}

    /* ── Tablet (640 – 1023 px) ── */
    @media (max-width: 1023px) {{
      .thumb-cell {{ width: 100px; padding: 0.4rem; }}
      .thumb-cell img {{ width: 90px; height: 60px; }}
      .thumb-cell .no-thumb {{ width: 90px; height: 60px; }}
    }}

    /* ── Mobile (< 640 px) ── */
    @media (max-width: 639px) {{
      /* Header */
      header {{
        flex-direction: column;
        gap: 0.15rem;
        padding: 0.9rem 1rem;
      }}
      header h1 {{ font-size: 1.2rem; }}
      header .meta {{ font-size: 0.78rem; }}

      /* Controls */
      .controls {{
        padding: 0.6rem 1rem;
        gap: 0.5rem;
      }}
      .controls input[type="search"] {{ min-width: 0; width: 100%; flex: none; }}
      .controls select {{ flex: 1; }}
      .controls .separator {{ display: none; }}
      .date-range {{ width: 100%; justify-content: space-between; }}
      .date-range input[type="date"] {{ flex: 1; min-width: 0; }}
      .count {{ margin-left: 0; width: 100%; text-align: right; }}

      /* Turn table into cards */
      main {{ padding: 0.75rem 0; overflow-x: visible; }}
      table {{ box-shadow: none; border-radius: 0; }}
      table, tbody {{ display: block; }}
      thead {{ display: none; }}

      tbody tr:not(#no-results) {{
        display: grid;
        grid-template-columns: 110px 1fr;
        grid-template-areas:
          "thumb title"
          "thumb date"
          "thumb byline"
          "tags  tags";
        column-gap: 0.75rem;
        row-gap: 0.2rem;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid #e8e8e8;
        background: #fff;
        margin-bottom: 0;
      }}
      tbody tr:not(#no-results):hover {{ background: #fafafa; }}

      .thumb-cell {{
        grid-area: thumb;
        width: auto;
        padding: 0;
        text-align: left;
        vertical-align: top;
        align-self: start;
      }}
      .thumb-cell img {{ width: 100px; height: 67px; }}
      .thumb-cell .no-thumb {{ width: 100px; height: 67px; margin: 0; }}

      tbody tr:not(#no-results) td:nth-child(2) {{
        grid-area: title;
        padding: 0;
        vertical-align: top;
      }}
      tbody tr:not(#no-results) td[data-date] {{
        grid-area: date;
        padding: 0;
        font-size: 0.78rem;
        color: #888;
        align-self: start;
      }}
      tbody tr:not(#no-results) .byline-cell {{
        grid-area: byline;
        padding: 0;
        padding-top: 0.2rem;
        font-size: 0.75rem;
        color: #888;
        white-space: normal;
        width: auto;
        max-width: none;
      }}
      .tags-cell {{
        grid-area: tags;
        padding: 0;
        padding-top: 0.4rem;
      }}

      #no-results td {{ display: block; }}
    }}
  </style>
</head>
<body>

<header>
  <h1>BBC Scrolly Tracker</h1>
  <span class="meta">BBC Visual Journalism &mdash; scrollytelling articles</span>
</header>

<div class="controls">
  <input type="search" id="search" placeholder="Filter by title, subtitle or byline…">
  <label>Topic</label>
  <select id="topic-filter">
    <option value="">All</option>
{topic_options}
  </select>
  <div class="separator"></div>
  <label>Component</label>
  <select id="component-filter">
    <option value="">All</option>
{component_options}
  </select>
  <div class="separator"></div>
  <div class="date-range">
    <label>From</label>
    <input type="date" id="date-from" min="{date_min}" max="{date_max}">
    <label>To</label>
    <input type="date" id="date-to" min="{date_min}" max="{date_max}">
  </div>
  <button class="clear-btn" id="clear-filters">✕ Clear filters</button>
  <span class="count" id="count">{count} articles</span>
</div>

<main>
  <table id="articles">
    <thead>
      <tr>
        <th></th>
        <th data-col="title">Title</th>
        <th data-col="date">Published</th>
        <th data-col="byline">Byline</th>
        <th>Tags</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
      <tr id="no-results" class="hidden">
        <td colspan="5" class="no-results-msg">No articles match your filters.</td>
      </tr>
    </tbody>
  </table>
</main>

<footer>
  Last updated: {updated} &mdash;
  Data collected for educational research.
  Articles &copy; BBC.
</footer>

<script>
  const tbody = document.querySelector('#articles tbody');
  const searchEl = document.getElementById('search');
  const topicEl = document.getElementById('topic-filter');
  const componentEl = document.getElementById('component-filter');
  const dateFromEl = document.getElementById('date-from');
  const dateToEl = document.getElementById('date-to');
  const countEl = document.getElementById('count');
  const noResults = document.getElementById('no-results');
  const clearBtn = document.getElementById('clear-filters');

  function filterRows() {{
    const q = searchEl.value.toLowerCase();
    const topic = topicEl.value;
    const component = componentEl.value;
    const dateFrom = dateFromEl.value;
    const dateTo = dateToEl.value;
    let visible = 0;
    tbody.querySelectorAll('tr:not(#no-results)').forEach(row => {{
      const text = (row.querySelector('td:nth-child(2)').textContent + ' ' + row.querySelector('.byline-cell').textContent).toLowerCase();
      const topics = JSON.parse(row.dataset.topics || '[]');
      const components = JSON.parse(row.dataset.components || '[]');
      const rowDate = row.querySelector('td[data-date]').dataset.date || '';
      const match =
        (!q || text.includes(q)) &&
        (!topic || topics.includes(topic)) &&
        (!component || components.includes(component)) &&
        (!dateFrom || rowDate >= dateFrom) &&
        (!dateTo || rowDate <= dateTo);
      row.classList.toggle('hidden', !match);
      if (match) visible++;
    }});
    countEl.textContent = visible + ' article' + (visible !== 1 ? 's' : '');
    noResults.classList.toggle('hidden', visible > 0);
  }}

  clearBtn.addEventListener('click', () => {{
    searchEl.value = '';
    topicEl.value = '';
    componentEl.value = '';
    dateFromEl.value = '';
    dateToEl.value = '';
    filterRows();
  }});

  searchEl.addEventListener('input', filterRows);
  topicEl.addEventListener('change', filterRows);
  componentEl.addEventListener('change', filterRows);
  dateFromEl.addEventListener('change', filterRows);
  dateToEl.addEventListener('change', filterRows);

  // Sortable columns
  let sortCol = null;
  let sortDir = 1;

  function applySort(col, dir) {{
    sortCol = col;
    sortDir = dir;
    document.querySelectorAll('thead th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
    const th = document.querySelector(`thead th[data-col="${{col}}"]`);
    th.classList.add(dir === 1 ? 'sorted-asc' : 'sorted-desc');
    const rows = Array.from(tbody.querySelectorAll('tr:not(#no-results)'));
    rows.sort((a, b) => {{
      let av, bv;
      if (col === 'date') {{
        av = a.querySelector('td[data-date]').dataset.date || '';
        bv = b.querySelector('td[data-date]').dataset.date || '';
      }} else if (col === 'byline') {{
        av = a.querySelector('.byline-cell').textContent.toLowerCase();
        bv = b.querySelector('.byline-cell').textContent.toLowerCase();
      }} else {{
        av = a.querySelector('td:nth-child(2) a').textContent.toLowerCase();
        bv = b.querySelector('td:nth-child(2) a').textContent.toLowerCase();
      }}
      return av < bv ? -dir : av > bv ? dir : 0;
    }});
    rows.forEach(r => tbody.insertBefore(r, noResults));
  }}

  document.querySelectorAll('thead th[data-col]').forEach(th => {{
    th.addEventListener('click', () => {{
      const col = th.dataset.col;
      const dir = (sortCol === col) ? sortDir * -1 : 1;
      applySort(col, dir);
    }});
  }});

  // Default: newest first
  applySort('date', -1);
</script>

</body>
</html>
"""


def main():
    articles = load_articles()
    if not articles:
        print("No articles found in data/articles.json — run scraper.py first.")
        return

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    html = render(articles)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"Dashboard written to {OUTPUT_FILE} ({len(articles)} articles)")


if __name__ == "__main__":
    main()
