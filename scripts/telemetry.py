#!/usr/bin/env python3
"""Regenerate assets/telemetry.svg and assets/status.svg from live GitHub data."""
import datetime
import html
import json
import os
import sys
import urllib.request

LOGIN = "CrimsonSithria"
ROOT = os.path.join(os.path.dirname(__file__), "..", "assets")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def api(url, payload=None):
    headers = {"Authorization": f"bearer {TOKEN}", "Accept": "application/vnd.github+json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch():
    user = api("https://api.github.com/graphql", {"query": QUERY, "variables": {"login": LOGIN}})["data"]["user"]
    coll = user["contributionsCollection"]
    days = [d for w in coll["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]

    streak, idx = 0, len(counts) - 1
    if counts and counts[-1] == 0:  # today isn't over yet — don't break the streak on it
        idx -= 1
    while idx >= 0 and counts[idx] > 0:
        streak += 1
        idx -= 1

    try:
        open_prs = api(f"https://api.github.com/search/issues?q=author:{LOGIN}+type:pr+state:open")["total_count"]
    except Exception:
        open_prs = None

    return {
        "followers": user["followers"]["totalCount"],
        "year_total": coll["contributionCalendar"]["totalContributions"],
        "sealed": coll["restrictedContributionsCount"] > 0,
        "last7": sum(counts[-7:]),
        "last14": counts[-14:],
        "streak": streak,
        "open_prs": open_prs,
    }


def leader(label, value):
    return html.escape(f"▸ {label} ".ljust(36, "·")), html.escape(f" {value}")


def wheel(x, y, digits, dur, phase):
    """One countdown digit column: stacked glyphs scrolled by a discrete SMIL translate."""
    lh = 20
    stack = "".join(
        f'<text x="{x}" y="{y + i * lh}" font-size="15" fill="#ffb3c0">{g}</text>' for i, g in enumerate(digits)
    )
    values = ";".join(f"0 {-i * lh}" for i in range(len(digits)))
    cid = f"w{x}"
    return (
        f'<clipPath id="{cid}"><rect x="{x - 1}" y="{y - 14}" width="12" height="18"/></clipPath>'
        f'<g clip-path="url(#{cid})"><g>'
        f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" '
        f'values="{values}" dur="{dur}s" begin="-{phase:.1f}s" repeatCount="indefinite"/>'
        f"{stack}</g></g>"
    )


def countdown(x, y, now):
    """T-H:MM:SS to the next 6h cron boundary, ticking in real time."""
    period = 6 * 3600
    day_s = now.hour * 3600 + now.minute * 60 + now.second
    r0 = period - ((day_s + 0.5) % period)  # half-step off the SMIL boundaries; keeps r0 in (0, period]
    wheels = [  # (offset_x, digit sequence, own period)
        (0, "543210", period),
        (24, "543210", 3600),
        (36, "9876543210", 600),
        (60, "543210", 60),
        (72, "9876543210", 10),
    ]
    parts = [f'<text x="{x + 12}" y="{y}" font-size="15" fill="#ffb3c0">:</text>'
             f'<text x="{x + 48}" y="{y}" font-size="15" fill="#ffb3c0">:</text>']
    for dx, digits, p in wheels:
        phase = (p - (r0 % p)) % p
        parts.append(wheel(x + dx, y, digits, p, phase))
    return "".join(parts)


def render_telemetry(d, now):
    rows = [
        leader("SYNC", now.strftime("%Y-%m-%d %H:%M UTC")),
        leader("CONTRIBUTIONS / 7D", d["last7"]),
        leader("CURRENT STREAK", f"{d['streak']} days"),
        leader("CONTRIBUTIONS / 365D", d["year_total"]),
        leader("OPEN PRS / PUBLIC BAND", d["open_prs"] if d["open_prs"] is not None else "—"),
        leader("SEALED TRAFFIC", "woven into counts" if d["sealed"] else "not broadcast"),
    ]
    lines = "\n".join(
        f'  <text x="36" y="{96 + i * 30}" font-size="14.5" fill="#9a6b76">{lab}'
        f'<tspan fill="#ffe4e8">{val}</tspan></text>'
        for i, (lab, val) in enumerate(rows)
    )

    vals = d["last14"]
    peak = max(max(vals), 1)
    bars = []
    for i, v in enumerate(vals):
        h = max(round(v / peak * 118), 3)
        x = 646 + i * 19
        bars.append(
            f'    <rect class="bar" x="{x}" y="{234 - h}" width="13" height="{h}" rx="2" '
            f'fill="#d92646" opacity="{0.45 + 0.55 * v / peak:.2f}" style="animation-delay:{i * 0.09:.2f}s"/>'
        )
    bars = "\n".join(bars)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 310" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" role="img" aria-label="fleet telemetry">
  <style>
    @keyframes blink{{0%,45%{{opacity:1}}50%,100%{{opacity:0}}}}
    .cur{{animation:blink 1.1s steps(1) infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
    .dot{{animation:pulse 2.2s ease-in-out infinite}}
    @keyframes sweep{{from{{transform:translateY(-10px)}}to{{transform:translateY(320px)}}}}
    .sweep{{animation:sweep 8s linear infinite}}
    @keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
    .bar{{transform-box:fill-box;transform-origin:bottom;animation:grow .9s ease-out both}}
  </style>
  <rect x="1" y="1" width="938" height="308" rx="12" fill="#0a040d" stroke="#ff2a4d" stroke-opacity=".32"/>
  <clipPath id="panel"><rect x="1" y="1" width="938" height="308" rx="12"/></clipPath>
  <g clip-path="url(#panel)"><rect class="sweep" width="940" height="3" fill="#ff5c72" opacity=".05"/></g>
  <text x="36" y="42" font-size="15" letter-spacing="2" fill="#ff5c72" font-weight="bold">OSIRIS // FLEET TELEMETRY</text>
  <text x="904" y="42" font-size="12.5" letter-spacing="1.5" fill="#9a6b76" text-anchor="end">CRIMSONSITHRIA · LIVE <tspan class="dot" fill="#ff3b5c">●</tspan></text>
  <line x1="24" y1="58" x2="916" y2="58" stroke="#ff2a4d" stroke-opacity=".18"/>
{lines}
  <text x="646" y="96" font-size="11.5" letter-spacing="2" fill="#9a6b76">ACTIVITY // 14D</text>
{bars}
  <line x1="644" y1="235" x2="912" y2="235" stroke="#ff2a4d" stroke-opacity=".3"/>
  <text x="36" y="284" font-size="13" letter-spacing="1" fill="#6e4a53">&gt; NEXT SYNC&#160;&#160;T-</text>
  {countdown(176, 284, now)}
  <text x="292" y="284" font-size="13" fill="#6e4a53">UTC · cadence 6h <tspan class="cur" fill="#ff5c72">█</tspan></text>
</svg>
"""


CORPUS = [
    "fleet nominal · memory persistent · the dawn is kept",
    "all agents accounted for · horizon stable",
    "factory humming · nothing forgotten",
    "signal clean · watching the horizon",
    "sync green · the sky still holds the dawn",
    "no ghosts in the fleet tonight",
    "uptime measured in dawns",
]


def typed(text, x, y, size, fill, begin, cps=18.0):
    """A text element revealed character-by-character via a SMIL-animated clip."""
    n = len(text)
    cw = size * 0.62
    dur = n / cps
    cid = f"t{x}x{y}"
    values = ";".join(f"{i * cw:.1f}" for i in range(n + 1))
    return f"""  <clipPath id="{cid}"><rect x="{x}" y="{y - size}" width="0" height="{size * 1.5:.0f}">
    <animate attributeName="width" calcMode="discrete" fill="freeze" begin="{begin}s" dur="{dur:.2f}s" values="{values}"/>
  </rect></clipPath>
  <g clip-path="url(#{cid})"><text x="{x}" y="{y}" font-size="{size}" fill="{fill}">{html.escape(text)}</text></g>"""


def render_status(now):
    line = CORPUS[now.timetuple().tm_yday % len(CORPUS)]
    cmd = typed("$ osiris --status", 36, 40, 15, "#ffe4e8", 0.5)
    reply = typed("> " + line, 36, 68, 15, "#c97f8d", 2.0)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 92" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" role="img" aria-label="osiris status">
  <style>@keyframes blink{{0%,45%{{opacity:1}}50%,100%{{opacity:0}}}}.cur{{animation:blink 1.1s steps(1) infinite}}</style>
  <rect x="1" y="1" width="938" height="90" rx="12" fill="#0a040d" stroke="#ff2a4d" stroke-opacity=".32"/>
{cmd}
{reply}
  <text x="{36 + (len(line) + 2) * 15 * 0.62:.0f}" y="68" font-size="15" class="cur" fill="#ff5c72">█</text>
</svg>
"""


def main():
    if not TOKEN:
        sys.exit("no GH_TOKEN / GITHUB_TOKEN in environment")
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        data = fetch()
    except Exception as e:  # keep the last good panels rather than publish a broken one
        print(f"::warning title=telemetry fetch failed::keeping previous assets: {e}")
        return
    with open(os.path.join(ROOT, "telemetry.svg"), "w") as f:
        f.write(render_telemetry(data, now))
    with open(os.path.join(ROOT, "status.svg"), "w") as f:
        f.write(render_status(now))
    print(f"telemetry updated: {json.dumps({k: v for k, v in data.items() if k != 'last14'})}")


if __name__ == "__main__":
    main()
