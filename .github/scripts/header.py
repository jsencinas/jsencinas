#!/usr/bin/env python3
"""Generate assets/header.svg: the animated terminal header of the profile README.

It copies the website (jsencinas.github.io) with SVG and CSS only, because GitHub
shows README images as <img>, which runs no JavaScript and loads no outside files:

- type: the name is set like the site's hero, Archivo 56px at -0.035em tracking,
  on one line, with the last names in gray (the hero's second line). Archivo and Geist Mono are embedded as base64
  (assets/fonts, SIL Open Font License), so GitHub draws the same fonts as the site.
- terminal (page.js): the command is typed 95 ms per letter after 500 ms, then the
  output rows come in 260 ms apart (360 ms fade and 6 px rise) and the cursor moves
  down to the last prompt; the cursor blinks every 1.06 s
- name (decrypt.js): every letter scrambles in its own color at 55% opacity,
  swapping every 55 ms, and the letters lock left to right in 60 ms per letter
  (from 1.3 to 2.6 s), with 90 ms of random spread, starting 200 ms in.
  Each letter has a fixed x, so nothing moves when it locks.

Letter positions come from header-metrics.json, measured in a browser with
canvas measureText (kerning on) on assets/fonts/archivo-var.woff2, for the whole
name as one line; "pos" holds the first names and the last names as two groups. Measure again
if the name, font, size or tracking changes.

Run from the repo root:  python3 .github/scripts/header.py
"""
import base64
import json
import random
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M = json.loads((ROOT / '.github/scripts/header-metrics.json').read_text(encoding='utf-8'))

# ---------- timing, in ms (same values as the website) ----------
TYPE_DELAY = 500      # page.js termDelayMs
TYPE_EVERY = 95       # page.js typeEveryMs
ROW_EVERY = 260       # page.js rowEveryMs
SWAP_EVERY = 55       # decrypt.js swapEveryMs
JITTER = 90           # decrypt.js jitterMs
LOCK_DELAY = 200      # page.js titleDelayMs
MS_PER_CHAR, MIN_MS, MAX_MS = 60, 1300, 2600
DIM = 0.55            # --decrypt-dim
TIMELINE = 4000       # shared length of the step animation

# ---------- colors (site.css) ----------
TEXT, TEXT_2 = '#F3F1EC', 'rgba(243,241,236,.70)'

# ---------- letters (decrypt.js scrambleFor) ----------
NARROW, WIDE_L, WIDE_U = 'fijlrt1', 'mw', 'MW'
UPPER = 'ABCDEFGHKLNOPRSTUVXYZ023456789'
LOWER = 'abcdeghknopqsuvxyz023456789'


def scramble(ch, rnd):
    if ch in 'fijlrtI1:.,-':
        s = NARROW
    elif ch in 'mw':
        s = WIDE_L
    elif ch in 'MW':
        s = WIDE_U
    elif ch != ch.lower():
        s = UPPER
    else:
        s = LOWER
    return rnd.choice(s)


CMD = 'whoami'
CMD_PITCH = 9         # Geist Mono advance at 15px (0.6 em)
NAME_X = 40
LINES = [(152, TEXT), (152, TEXT_2)]   # baseline and color of each group: one line, last names in gray

type_end = TYPE_DELAY + len(CMD) * TYPE_EVERY
t_name = type_end + ROW_EVERY          # first output row: the name, already scrambling
t_meta = t_name + ROW_EVERY            # second row
t_end = t_meta + ROW_EVERY             # last prompt, the cursor moves here

# every letter of both groups, in reading order, as decrypt.js walks the title
letters = []
for li, line in enumerate(M['pos']):
    for p in line:
        if p['c'] != ' ':
            letters.append({'line': li, 'c': p['c'], 'x': NAME_X + p['x'], 'mid': NAME_X + p['x'] + p['adv'] / 2})

rnd = random.Random(7102)
n = len(letters)
dur = min(MAX_MS, max(MIN_MS, n * MS_PER_CHAR))
for k, L in enumerate(letters):
    L['lock'] = t_name + LOCK_DELAY + (k + 1) / n * dur + (rnd.random() - 0.5) * JITTER
t_final = max(L['lock'] for L in letters)

frames = []
t = t_name
while t < t_final:
    frames.append(t)
    t += SWAP_EVERY


def pct(ms):
    return f'{ms / TIMELINE * 100:.3f}%'


def line_text(glyphs, li):
    """One group as tspans of runs; every glyph carries its own x."""
    y, color = LINES[li]
    runs, cur = [], None
    for ch, x, dim in glyphs:
        if cur is None or cur[0] != dim:
            cur = [dim, [], []]
            runs.append(cur)
        cur[1].append(ch)
        cur[2].append(f'{x:.2f}')
    spans = ''.join(
        f'<tspan{" class=\"x\"" if dim else ""} x="{" ".join(xs)}">{escape("".join(chs))}</tspan>'
        for dim, chs, xs in runs)
    return f'<text class="name" y="{y}" fill="{color}">{spans}</text>'


def frame(t):
    out = []
    for li in range(len(LINES)):
        glyphs = []
        for L in letters:
            if L['line'] != li:
                continue
            if t >= L['lock']:
                glyphs.append((L['c'], L['x'], False))
            else:
                s = scramble(L['c'], rnd)
                glyphs.append((s, L['mid'] - M['adv'][s] / 2, True))   # centered on the letter, as decrypt.js
        out.append(line_text(glyphs, li))
    return ''.join(out)


final = ''.join(line_text([(L['c'], L['x'], False) for L in letters if L['line'] == li], li) for li in range(len(LINES)))
cmd_xs = ' '.join(str(160 + CMD_PITCH * i) for i in range(len(CMD)))


def font(path):
    return base64.b64encode((ROOT / path).read_bytes()).decode()


kf, groups = [], []
for k, t in enumerate(frames):
    end = frames[k + 1] if k + 1 < len(frames) else t_final
    kf.append(f'    @keyframes f{k} {{ 0% {{ opacity: 0; }} {pct(t)} {{ opacity: 1; }} {pct(end)} {{ opacity: 0; }} 100% {{ opacity: 0; }} }}\n'
              f'    .f{k} {{ animation-name: f{k}; }}')
    groups.append(f'    <g class="f f{k}">{frame(t)}</g>')
kf.append(f'    @keyframes final {{ 0% {{ opacity: 0; }} {pct(t_final)} {{ opacity: 1; }} 100% {{ opacity: 1; }} }}\n'
          f'    .final {{ animation-name: final; }}')
# the typing cursor is visible from the start until it moves down to the last prompt
kf.append(f'    @keyframes gone {{ 0% {{ visibility: visible; }} {pct(t_end)} {{ visibility: hidden; }} 100% {{ visibility: hidden; }} }}')

NAME = ' '.join(''.join(p['c'] for p in line) for line in M['pos'])
H = 264

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{H}" viewBox="0 0 860 {H}" role="img" aria-labelledby="t d">
  <title id="t">{NAME}</title>
  <desc id="d">Terminal: whoami. {NAME}. Computer Science at Tec de Monterrey, former FRC 7102 lead programmer, learning penetration testing.</desc>
  <!-- generated by .github/scripts/header.py, edit that file instead -->
  <style>
    @font-face {{ font-family: 'Archivo'; font-weight: 400 500; src: url(data:font/woff2;base64,{font('assets/fonts/archivo-var.woff2')}) format('woff2'); }}
    @font-face {{ font-family: 'Geist Mono'; font-weight: 400; src: url(data:font/woff2;base64,{font('assets/fonts/geist-mono-400.woff2')}) format('woff2'); }}
    .mono {{ font-family: 'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace; }}
    .prompt {{ fill: #D9C7A0; font-size: 15px; }}
    .cmd {{ fill: {TEXT}; font-size: 15px; }}
    .cap {{ fill: rgba(243,241,236,.56); font-size: 12px; letter-spacing: .08em; }}
    .name {{ font-family: Archivo,'Helvetica Neue',Helvetica,Arial,sans-serif; font-size: {M['size']}px; font-weight: 400; }}
    .name .x {{ fill-opacity: {DIM}; }}
    /* every frame runs on one shared timeline with step-end, so exactly one is visible at a time */
    .f, .final {{ opacity: 0; animation-duration: {TIMELINE}ms; animation-timing-function: step-end; animation-fill-mode: forwards; }}
{chr(10).join(kf)}
    .meta {{ fill: rgba(243,241,236,.56); font-size: 13px; }}
    .meta .sep {{ fill: rgba(243,241,236,.22); }}
    /* output rows: the terminal rows of the website (360 ms fade, 6 px rise, 260 ms apart) */
    .row {{ opacity: 0; animation: row 360ms cubic-bezier(.16,1,.3,1) forwards; }}
    .r1 {{ animation-delay: {t_name}ms; }}
    .r2 {{ animation-delay: {t_meta}ms; }}
    .r3 {{ animation-delay: {t_end}ms; }}
    /* typing: a cover over the command and the cursor step right one letter at a time */
    .cover {{ animation: type {len(CMD) * TYPE_EVERY}ms steps({len(CMD)}, end) {TYPE_DELAY}ms forwards; }}
    .tcur {{ animation: type {len(CMD) * TYPE_EVERY}ms steps({len(CMD)}, end) {TYPE_DELAY}ms forwards, gone {TIMELINE}ms step-end forwards; }}
    .cursor {{ fill: #D9C7A0; animation: blink 1.06s steps(1, end) infinite; }}
    @keyframes type {{ to {{ transform: translateX({len(CMD) * CMD_PITCH}px); }} }}
    @keyframes row {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .f, .cover, .tcur {{ display: none; }}
      .final, .row {{ opacity: 1; animation: none; }}
      .cursor {{ animation: none; }}
    }}
  </style>
  <rect x="0.5" y="0.5" width="859" height="{H - 1}" rx="14" fill="#0B0C0D" stroke="rgba(243,241,236,.14)"/>
  <path d="M0.5 40.5 H859.5" stroke="rgba(243,241,236,.10)"/>
  <circle cx="24" cy="20.5" r="5" fill="rgba(243,241,236,.18)"/>
  <circle cx="42" cy="20.5" r="5" fill="rgba(243,241,236,.18)"/>
  <circle cx="60" cy="20.5" r="5" fill="rgba(243,241,236,.18)"/>
  <text class="mono cap" x="430" y="25" text-anchor="middle">~/jsencinas</text>
  <text class="mono cap" x="836" y="25" text-anchor="end">GDL, MX</text>

  <text class="mono prompt" x="40" y="86">jorge@gdl:~$</text>
  <text class="mono cmd" x="{cmd_xs}" y="86">{CMD}</text>
  <rect class="cover" x="160" y="68" width="{len(CMD) * CMD_PITCH + 6}" height="26" fill="#0B0C0D"/>
  <g class="tcur"><rect class="cursor" x="160" y="73" width="9" height="18"/></g>

  <g class="row r1">
{chr(10).join(groups)}
    <g class="final">{final}</g>
  </g>

  <text class="mono meta row r2" x="40" y="200">CS @ Tec de Monterrey <tspan class="sep">/</tspan> ex lead programmer, FRC 7102 <tspan class="sep">/</tspan> learning pentesting on Hack The Box</text>

  <g class="row r3">
    <text class="mono prompt" x="40" y="240">jorge@gdl:~$</text>
    <rect class="cursor" x="160" y="227" width="9" height="18"/>
  </g>
</svg>
'''

(ROOT / 'assets/header.svg').write_text(svg, encoding='utf-8')
print(f'{len(frames)} frames, name locked at {t_final:.0f} ms, last prompt at {t_end} ms, {len(svg) // 1024} KB')
