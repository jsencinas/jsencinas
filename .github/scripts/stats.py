#!/usr/bin/env python3
"""Render assets/stats.svg from public GitHub data. Standard library only.

Usage: stats.py <username> <output.svg>
Reads GITHUB_TOKEN if set (only to raise the API rate limit).
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

USER, OUT = sys.argv[1], sys.argv[2]
TOKEN = os.environ.get("GITHUB_TOKEN")

MONO = "'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
BG, TEXT, ACCENT = "#0B0C0D", "#F3F1EC", "#D9C7A0"
LEVELS = ["rgba(243,241,236,.07)", "rgba(217,199,160,.30)", "rgba(217,199,160,.52)",
          "rgba(217,199,160,.76)", "#D9C7A0"]
LANG_SHADES = ["#D9C7A0", "#F3F1EC", "#9C8F73", "#8A8985", "#5F5846", "#4A4A48"]


def get(url, api=True):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-stats"})
    if api:
        req.add_header("Accept", "application/vnd.github+json")
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


# --- contributions: the public calendar page -------------------------------
page = get(f"https://github.com/users/{USER}/contributions", api=False)
cells = {}  # element id -> (date, level)
for td in re.findall(r"<td[^>]*data-date[^>]*>", page):
    cells[re.search(r'id="([^"]+)"', td).group(1)] = (
        dt.date.fromisoformat(re.search(r'data-date="([^"]+)"', td).group(1)),
        int(re.search(r'data-level="(\d)"', td).group(1)),
    )
counts = {}
for cid, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)', page):
    if cid in cells:
        m = re.match(r"\s*(\d[\d,]*) contribution", label)
        counts[cells[cid][0]] = int(m.group(1).replace(",", "")) if m else 0
days = sorted((d, lvl, counts.get(d, 0)) for d, lvl in cells.values())
if len(days) < 300:
    sys.exit(f"contribution calendar looks wrong ({len(days)} days); keeping the old card")
total = sum(c for _, _, c in days)

longest = run = 0
for _, _, c in days:
    run = run + 1 if c else 0
    longest = max(longest, run)
current = 0
tail = days[:-1] if days[-1][2] == 0 else days  # today may still be empty
for _, _, c in reversed(tail):
    if not c:
        break
    current += 1

# --- repositories and languages ---------------------------------------------
repos = [r for r in json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner"))
         if not r["fork"]]
langs = {}
for r in repos:
    for name, size in json.loads(get(r["languages_url"])).items():
        langs[name] = langs.get(name, 0) + size
lang_total = sum(langs.values()) or 1
top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
shown = sum(v for _, v in top) or 1

# --- drawing -----------------------------------------------------------------
W, PAD = 860, 40
INNER = W - 2 * PAD
first = days[0][0]
start = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # Sunday of the first week
weeks = (days[-1][0] - start).days // 7 + 1
PITCH = INNER / weeks
CELL = PITCH - 2.6
GY = 86

grid, months, seen = [], [], set()
for d, lvl, c in days:
    col, row = (d - start).days // 7, (d.weekday() + 1) % 7
    grid.append(f'<rect class="c" style="animation-delay:{col * 14}ms" x="{PAD + col * PITCH:.1f}" '
                f'y="{GY + row * PITCH:.1f}" width="{CELL:.1f}" height="{CELL:.1f}" rx="2.5" fill="{LEVELS[lvl]}"/>')
    if d.day <= 7 and (d.year, d.month) not in seen and col < weeks - 2:
        seen.add((d.year, d.month))
        months.append(f'<text class="cap" x="{PAD + col * PITCH:.1f}" y="{GY - 10}">{d.strftime("%b").upper()}</text>')

SY = GY + 7 * PITCH + 44
facts = [(f"{total:,}", "contributions, last year"), (f"{current}d", "current streak"),
         (f"{longest}d", "longest streak"), (str(len(repos)), "public repos")]
stat = []
for i, (num, cap) in enumerate(facts):
    x = PAD + i * INNER / 4
    stat.append(f'<g class="rise" style="animation-delay:{900 + i * 110}ms">'
                f'<text class="num" x="{x:.0f}" y="{SY:.0f}">{num}</text>'
                f'<text class="cap" x="{x:.0f}" y="{SY + 22:.0f}">{cap.upper()}</text></g>')

BY = SY + 54
bar, legend, x, lx = [], [], PAD, PAD
for i, (name, size) in enumerate(top):
    w = INNER * size / shown
    bar.append(f'<rect x="{x:.1f}" y="{BY:.0f}" width="{max(w - 2, 1):.1f}" height="8" rx="2" fill="{LANG_SHADES[i]}"/>')
    x += w
    label = f"{name} {100 * size / lang_total:.0f}%"
    legend.append(f'<circle cx="{lx + 4:.0f}" cy="{BY + 30:.0f}" r="4" fill="{LANG_SHADES[i]}"/>'
                  f'<text class="leg" x="{lx + 14:.0f}" y="{BY + 34:.0f}">{html.escape(label)}</text>')
    lx += 14 + len(label) * 7.6 + 22
H = BY + 62
NL = "\n    "

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="GitHub activity for {USER}: {total} contributions in the last year, current streak {current} days, longest streak {longest} days, {len(repos)} public repositories. Top languages: {html.escape(", ".join(n for n, _ in top))}.">
  <style>
    text {{ font-family: {MONO}; }}
    .prompt {{ fill: {ACCENT}; font-size: 15px; }}
    .cmd {{ fill: {TEXT}; font-size: 15px; }}
    .cap {{ fill: rgba(243,241,236,.50); font-size: 11px; letter-spacing: .08em; }}
    .num {{ fill: {TEXT}; font-size: 28px; font-weight: 500; }}
    .leg {{ fill: rgba(243,241,236,.72); font-size: 12.5px; }}
    .c {{ opacity: 0; animation: on .35s ease-out forwards; }}
    .rise {{ opacity: 0; animation: rise .7s cubic-bezier(.16,1,.3,1) forwards; }}
    .bar {{ transform-box: fill-box; transform-origin: left center; transform: scaleX(0); animation: grow 1s cubic-bezier(.16,1,.3,1) 1.3s forwards; }}
    .late {{ animation-delay: 1.7s; }}
    @keyframes on {{ to {{ opacity: 1; }} }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes grow {{ to {{ transform: scaleX(1); }} }}
    @media (prefers-reduced-motion: reduce) {{
      .c, .rise {{ opacity: 1; animation: none; }}
      .bar {{ transform: none; animation: none; }}
    }}
  </style>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1:.0f}" rx="14" fill="{BG}" stroke="rgba(243,241,236,.14)"/>
  <text class="prompt" x="{PAD}" y="42">jorge@gdl:~$</text>
  <text class="cmd" x="{PAD + 120}" y="42">git log --since="1 year ago" --stat</text>
  <g>
    {NL.join(months)}
    {NL.join(grid)}
  </g>
  {NL.join(stat)}
  <g class="bar">
    {NL.join(bar)}
  </g>
  <g class="rise late">
    {NL.join(legend)}
  </g>
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)
print(f"{total} contributions, streak {current}/{longest}, {len(repos)} repos, langs: "
      + ", ".join(f"{n} {100 * s / lang_total:.0f}%" for n, s in top))
