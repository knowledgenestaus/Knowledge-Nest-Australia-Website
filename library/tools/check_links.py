#!/usr/bin/env python3
"""Checks every link published in the library and reports the ones that no longer load.

Usage: python3 library/tools/check_links.py [--report report.md]
Exits with status 1 when any link is dead, so an automated run can raise the alarm.
Sites that refuse automated visitors are listed separately; they are not treated as dead.
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = json.load(open(os.path.join(ROOT, "library", "data", "library.json"), encoding="utf8"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; KnowledgeNestLinkCheck/1.0; +https://knowledgenest.com.au/library.html)",
      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


def links():
    seen = {}
    for x in DATA["entries"]:
        seen.setdefault(x["url"], x["title"])
    for s in DATA["shows"]:
        for key in ("url", "spotify", "apple"):
            if s.get(key):
                seen.setdefault(s[key], s["title"])
    return seen


def check(item):
    url, title = item
    target = urllib.request.quote(url, safe=":/?&=%#+,;@~!$'()*")  # some links contain spaces
    m = re.search(r"(?:youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})", url)
    if m and "youtu" in url:
        target = "https://www.youtube.com/oembed?format=json&url=" + urllib.request.quote(url, safe="")
    try:
        req = urllib.request.Request(target, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(4000).decode("utf8", "ignore")
            if re.search(r"<title[^>]*>[^<]*(page not found|404)", body, re.I):
                return url, title, "dead", "page says not found"
            return url, title, "ok", str(r.status)
    except urllib.error.HTTPError as err:
        if err.code in (404, 410) or (target != url and err.code == 400):
            return url, title, "dead", str(err.code)
        if err.code in (401, 403, 405, 406, 429, 999):
            return url, title, "blocked", str(err.code)
        return url, title, "unsure", str(err.code)
    except Exception as err:  # timeouts, DNS, TLS
        return url, title, "unsure", type(err).__name__


def main():
    items = list(links().items())
    with cf.ThreadPoolExecutor(12) as pool:
        results = list(pool.map(check, items))
    groups = {"dead": [], "unsure": [], "blocked": [], "ok": []}
    for r in results:
        groups[r[2]].append(r)
    lines = ["# Library link check", "", "%d links checked: %d fine, %d dead, %d unsure, %d refused the automated check."
             % (len(results), len(groups["ok"]), len(groups["dead"]), len(groups["unsure"]), len(groups["blocked"])), ""]
    for key, heading in (("dead", "Dead links (remove or replace)"), ("unsure", "Could not be reached this time (check by hand)"),
                         ("blocked", "Refused the automated check (usually fine in a browser)")):
        if groups[key]:
            lines += ["## " + heading, ""] + ["- %s: <%s> (%s)" % (t, u, why) for u, t, _, why in groups[key]] + [""]
    report = "\n".join(lines)
    print(report)
    if "--report" in sys.argv:
        open(sys.argv[sys.argv.index("--report") + 1], "w", encoding="utf8").write(report)
    sys.exit(1 if groups["dead"] else 0)


if __name__ == "__main__":
    main()
