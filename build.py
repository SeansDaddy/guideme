#!/usr/bin/env python3
"""Build Guide Me Xian static site from Markdown articles."""

import os, re, json
from pathlib import Path
import markdown
from jinja2 import Template

# ── Config ──────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
OUT_DIR   = BASE_DIR / "out"
TMPL_DIR  = BASE_DIR / "templates"
ARTICLE_DIR = BASE_DIR / "articles"

CATEGORY_COLORS = {
    "城垣与防御":  "8b6914",
    "宫廷与遗址":  "6b3fa0",
    "宗教与社区":  "7e5109",
    "历史街区":    "1a5e63",
    "博物馆与墓葬": "b74611",
    "近现代空间":  "2e6b4f",
    "自然与当代":  "2e86ab",
}

# ── Markdown preprocessing ──────────────────────────────────────────
# Extract frontmatter: lines starting with ---
def parse_frontmatter(text):
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text
    kv = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        k, _, v = lines[i].partition(":")
        kv[k.strip()] = v.strip()
        i += 1
    body = "\n".join(lines[i+1:])
    return kv, body

# Simple markdown-to-html (basic, no extensions needed for our articles)
md = markdown.Markdown(extensions=["fenced_code", "tables"])

def md_to_html(text):
    html = md.convert(text)
    md.reset()
    return html

# ── Load template ───────────────────────────────────────────────────
def t(name):
    return (TMPL_DIR / name).read_text(encoding="utf-8")

# ── Article slug from filename ───────────────────────────────────────
def slug_of(fname):
    return fname.stem          # e.g. "dayan_tower" from "dayan_tower.md"

# ── Build city map data ──────────────────────────────────────────────
def build_index_articles(all_articles):
    """Organize articles by category for the index page."""
    groups = {}
    for a in all_articles:
        g = a["category"]
        groups.setdefault(g, []).append(a)
    return groups

# ── Main build ───────────────────────────────────────────────────────
def build():
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "xian").mkdir(exist_ok=True)
    (OUT_DIR / "static").mkdir(exist_ok=True)

    # Copy static assets
    shutil.copy(BASE_DIR / "static" / "style.css", OUT_DIR / "static" / "style.css")

    # Collect all articles
    all_articles = []

    for md_file in sorted(ARTICLE_DIR.glob("*.md")):
        slug = slug_of(md_file)
        raw  = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)

        # Build article dict
        lat = float(fm.get("lat", 34.25))
        lng = float(fm.get("lng", 108.96))

        art = {
            "slug":               slug,
            "title":              fm.get("title", slug),
            "subtitle":          fm.get("subtitle", ""),
            "category":          fm.get("category", ""),
            "category_color":    CATEGORY_COLORS.get(fm.get("category", ""), "555555"),
            "lat":               lat,
            "lng":               lng,
            "article_title_plain": fm.get("title", slug).replace('"', '\\"').replace('\u201c', '\\"').replace('\u201d', '\\"'),
            "description":        fm.get("description", fm.get("subtitle", "")),
            "body":              md_to_html(body),
            "canonical_url":     f"https://xian.guideme.city/xian/{slug}/",
        }
        all_articles.append(art)

        # Render article HTML
        tmpl = Template(t("article.html"))
        html = tmpl.render(**art)
        out_path = OUT_DIR / "xian" / slug / "index.html"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"  ✓ /xian/{slug}/")

    # ── Index page ──────────────────────────────────────────────────
    groups = build_index_articles(all_articles)
    group_colors_list = [CATEGORY_COLORS.get(g, "555555") for g in groups.keys()]

    tmpl = Template(t("index.html"))
    html = tmpl.render(
        article_count    = len(all_articles),
        articles_by_group = groups,
        group_colors     = group_colors_list,
        all_articles     = all_articles,
    )
    (OUT_DIR / "xian" / "index.html").write_text(html, encoding="utf-8")
    print(f"  ✓ /xian/ (index)")

    # ── Root redirect ───────────────────────────────────────────────
    root = OUT_DIR / "index.html"
    root.write_text(
        "<!DOCTYPE html><html><head>"
        '<meta http-equiv="refresh" content="0;url=/xian/">'
        "</head><body><a href='/xian/'>Guide Me Xian</a></body></html>",
        encoding="utf-8"
    )
    print("  ✓ / (redirect → /xian/)")

    print(f"\nBuild complete → {OUT_DIR}/")
    print(f"  {len(all_articles)} articles")

# ── Entry ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import shutil
    build()
