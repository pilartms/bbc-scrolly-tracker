# BBC Scrolly Tracker

A weekly-updated index of BBC Visual Journalism scrollytelling articles published since November 2024. The scraper discovers articles automatically by following cross-links between pieces, extracts metadata, and detects interactive components (3D, scrollable video, autoplay video). Results are published as a filterable dashboard via GitHub Pages.

Built as part of the **Advanced Prompt Engineering for Journalists** MOOC, taught by Joe Amditis (Center for Cooperative Media).

**Live dashboard:** https://pilartms.github.io/bbc-scrolly-tracker/

---

## Run locally

```bash
pip install -r requirements.txt

# Fetch new articles and update data/articles.json
python scraper.py

# Rebuild the dashboard at docs/index.html
python build_dashboard.py
```

Open `docs/index.html` in a browser to view the dashboard locally.

## Automatic updates

A GitHub Actions workflow runs every Monday at 08:00 UTC. It fetches any new articles, rebuilds the dashboard, and commits the updated `data/articles.json` and `docs/index.html` back to the repo. GitHub Pages picks up the changes automatically.

To trigger a run manually: **Actions → Weekly scrape → Run workflow**.

---

_Data collected for educational research. Articles © BBC._
