#!/usr/bin/env python3
"""This week's reading: sets the three featured Substack articles, or suggests candidates.

Set the week's picks (after Jo has approved them):

    python3 library/tools/feature_week.py URL URL URL --why "..." --why "..." --why "..."

  For each address it reads the post's title, author and lead image from Substack (<publication>/api/v1/posts/<slug>, or
  the page's own og tags if that fails), checks the post is free (audience "everyone" and no paywall wording on the page),
  and refuses any address featured in the last 12 weeks. It then moves the current week into the archive, writes
  library/data/featured.json and prints a summary. Nothing is written if any check fails.

  --why      one per address, in the same order: one or two sentences in Jo's voice on why it is worth reading
  --title    optional, one per address ("" keeps Substack's title): a shorter title for the card
  --week     the Monday the picks are for, YYYY-MM-DD (default: today if it is Monday in Melbourne, otherwise next Monday)
  --intro    optional line under the heading (default: keep the current one)
  --data     folder holding featured.json, library.json and substacks.json (default: library/data); use a copy to test
  --dry-run  check and print, but write nothing

Suggest candidates for the weekly picker:

    python3 library/tools/feature_week.py --suggest [--days 14]

  Reads library/data/substacks.json, pages through each Substack's archive (?sort=new&limit=25, then &cursor=...),
  and prints free articles from the last 14 days that are not already in the library and not featured recently.

Run from the site root. Uses Python's standard library only; HTTPS goes through any proxy set in the environment.
Then run python3 library/build.py (the "Library upkeep" workflow does this when the change reaches main).
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PAYWALL = ("Keep reading with a 7-day free trial", "This post is for paid subscribers", 'class="paywall')
REPEAT_WEEKS = 12
MELBOURNE = timezone(timedelta(hours=11))   # AEDT; near enough for choosing a Monday


def fetch(url, as_json=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json" if as_json else "text/html"})
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode("utf8", "replace")
    return json.loads(body) if as_json else body


def clean_url(url):
    u = urlparse(url.strip())
    return "https://%s%s" % (u.netloc.lower(), u.path.rstrip("/"))


def host(url):
    h = urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def tidy(text):
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    return text.replace("“", '"').replace("”", '"')


def load(data, name, default):
    path = os.path.join(data, name)
    return json.load(open(path, encoding="utf8")) if os.path.exists(path) else default


def credit(names, pub_title, url, catalogue):
    """"Author (Publication)", or the author alone when the publication is simply the author's name.
    Reuses the library's own wording when it already credits this author on this Substack."""
    author = " and ".join(names) if names else ""
    same = [x["by"] for x in catalogue if x.get("type") == "read" and host(x["url"]) == host(url) and author and x["by"].startswith(author)]
    if same:
        return max(set(same), key=same.count)
    if not author:
        return pub_title or host(url)
    bare = lambda s: re.sub(r"^(dr|prof|professor)\.?\s+", "", (s or "").strip(), flags=re.I).lower()
    if not pub_title or bare(pub_title) == bare(author):
        return author
    return "%s (%s)" % (author, pub_title)


def post_info(url, stacks, catalogue):
    """Title, credit, date and whether the post is free, from the Substack API, falling back to the page's tags."""
    u = urlparse(url)
    if "/p/" not in u.path:
        raise ValueError("not a Substack post address (no /p/ in it): %s" % url)
    slug = u.path.split("/p/", 1)[1].strip("/").split("/")[0]
    stack = next((s for s in stacks if host(s["url"]) == host(url)), None)
    info = {"url": clean_url(url), "audience": None, "problems": []}
    try:
        d = fetch("https://%s/api/v1/posts/%s" % (u.netloc, quote(slug)), as_json=True)
        info.update(title=tidy(d.get("title")), audience=d.get("audience"), date=(d.get("post_date") or "")[:10], cover=d.get("cover_image"),
                    names=[b["name"] for b in d.get("publishedBylines") or [] if b.get("name")],
                    kind=d.get("type"), url=clean_url(d.get("canonical_url") or url))
    except (urllib.error.URLError, ValueError, KeyError) as ex:
        info["problems"].append("Substack API did not answer (%s); used the page's tags" % ex)
    try:
        page = fetch(info["url"])
    except urllib.error.URLError as ex:
        raise ValueError("the page did not load: %s (%s)" % (url, ex))
    def tag(attr, name):
        m = re.search(r'<meta[^>]*%s="%s"[^>]*content="([^"]*)"' % (attr, name), page)
        return tidy(m.group(1)) if m else ""
    if not info.get("title"):
        info["title"] = tag("property", "og:title")
    if not info.get("names"):
        info["names"] = [n for n in [tag("name", "author")] if n]
    info["og"] = html.unescape(tag("property", "og:image"))
    info["image"], why_none = lead_image(info, u)
    if not info["image"]:
        info["problems"].append("no lead image (%s); the card shows the publication's name instead" % why_none)
    pub = stack["title"] if stack else tag("property", "og:site_name")
    info["by"] = credit(info["names"], pub, info["url"], catalogue)
    info["paywall"] = [m for m in PAYWALL if m in page]
    if info["audience"] not in (None, "everyone"):
        info["problems"].append("not free: Substack marks it '%s'" % info["audience"])
    if info["audience"] is None:
        info["problems"].append("could not confirm it is free from the API; the page shows %s" % ("paywall wording" if info["paywall"] else "no paywall wording"))
    if info["paywall"]:
        info["problems"].append("not free: the page says %r" % info["paywall"][0])
    if info.get("kind") and info["kind"] != "newsletter":
        info["problems"].append("this is a %s post, not an article" % info["kind"])
    return info


def original_image(url):
    """The image behind a substackcdn.com address (".../image/fetch/<options>/<encoded original>"), or the address itself."""
    m = re.match(r"https://substackcdn\.com/image/fetch/[^/]*/(https?%3A.*)$", url or "")
    return unquote(m.group(1)) if m else url


def card_image(orig):
    """The address to show on the card: Substack's image server at 600 pixels wide rather than the full-size original."""
    h = urlparse(orig).netloc
    if h == "substack-post-media.s3.amazonaws.com" or h.startswith("bucketeer-"):
        return "https://substackcdn.com/image/fetch/w_600,c_limit,f_auto,q_auto:good,fl_progressive:steep/" + quote(orig, safe="")
    if h == "images.unsplash.com":
        return re.sub(r"([?&])w=\d+", r"\1w=600", orig)
    return orig


def lead_image(info, u):
    """The post's own lead image, as library/data/thumbs.json records them: Substack's cover_image, or else the page's
    og:image. Refused (returns None and the reason) when it is the publication's share card, when more than two recent posts
    of the publication use the same picture (a default image), when it is under 400 pixels wide, or when it does not load
    as an image. Check the picture by eye before Jo approves: an advertisement is not caught here."""
    orig = original_image(info.get("cover") or info.get("og") or "")
    if not orig:
        return None, "the post has none"
    if "subscribe-card" in orig or "/twitter/" in orig:
        return None, "only the publication's share card"
    try:
        d = fetch("https://%s/api/v1/archive?sort=new&limit=25" % u.netloc, as_json=True)
        posts = d.get("posts", []) if isinstance(d, dict) else d
        same = sum(1 for p in posts if original_image(p.get("cover_image") or "") == orig)
        if same > 2:
            return None, "the same picture is on %d recent posts, so it is the publication's default" % same
    except (urllib.error.URLError, ValueError):
        pass
    size = re.search(r"_(\d+)x(\d+)\.\w+$", orig)
    if size and int(size.group(1)) < 400:
        return None, "it is only %s pixels wide" % size.group(1)
    image = card_image(orig)
    try:
        req = urllib.request.Request(image, headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/*"})
        with urllib.request.urlopen(req, timeout=40) as r:
            if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                return None, "it did not load as an image"
    except urllib.error.URLError as ex:
        return None, "it did not load (%s)" % ex
    return image, ""


def recent_urls(featured, week, weeks=REPEAT_WEEKS):
    """Addresses featured in the `weeks` weeks before `week` (the current picks count, unless they are for `week` itself)."""
    cutoff = week - timedelta(weeks=weeks)
    seen = {}
    for x in featured.get("archive", []):
        try:
            when = date.fromisoformat(x["week_of"])
        except (KeyError, ValueError):
            continue
        if cutoff <= when < week:
            seen[clean_url(x["url"])] = x["week_of"]
    if featured.get("week_of") and featured.get("week_of") != week.isoformat():
        try:
            if cutoff <= date.fromisoformat(featured["week_of"]):
                for x in featured.get("items", []):
                    seen[clean_url(x["url"])] = featured["week_of"]
        except ValueError:
            pass
    return seen


def next_monday():
    today = datetime.now(MELBOURNE).date()
    return today + timedelta(days=(7 - today.weekday()) % 7)


def style_notes(text):
    """The site's house rules for running text."""
    notes = []
    if "—" in text or " – " in text:
        notes.append("has a dash; reword (no em dashes)")
    if re.search(r":\s+[a-z]", text):
        notes.append("has a colon before a lower-case word; reword (the site would capitalise mid-sentence)")
    for us, au in (("color", "colour"), ("behavior", "behaviour"), ("organiz", "organis"), ("prioritiz", "prioritis"), (" math ", " maths "), ("center", "centre")):
        if us in text.lower():
            notes.append("American spelling '%s'; use '%s'" % (us.strip(), au.strip()))
    return notes


def set_week(args):
    data = args.data
    featured = load(data, "featured.json", {})
    catalogue = load(data, "library.json", {}).get("entries", [])
    stacks = load(data, "substacks.json", [])
    week = date.fromisoformat(args.week) if args.week else next_monday()
    if week.weekday() != 0:
        sys.exit("STOPPED: --week %s is not a Monday." % week)
    whys = args.why or []
    titles = args.title or []
    if len(whys) > len(args.urls) or len(titles) > len(args.urls):
        sys.exit("STOPPED: more --why or --title texts than addresses.")
    if len(set(clean_url(u) for u in args.urls)) != len(args.urls):
        sys.exit("STOPPED: the same address is given twice.")
    seen = recent_urls(featured, week)
    items, failed = [], []
    for i, url in enumerate(args.urls):
        try:
            info = post_info(url, stacks, catalogue)
        except ValueError as ex:
            failed.append("%s: %s" % (url, ex))
            continue
        hard = [p for p in info["problems"] if p.startswith("not free") or p.startswith("could not confirm")]
        free = not hard
        repeat = seen.get(info["url"]) or seen.get(clean_url(url))
        if repeat:
            hard.append("already featured in the week of %s (no repeats within %d weeks)" % (repeat, REPEAT_WEEKS))
        why = whys[i].strip() if i < len(whys) else ""
        title = titles[i].strip() if i < len(titles) and titles[i].strip() else info["title"]
        print("%d. %s\n   %s\n   %s, posted %s\n   free: %s%s" % (i + 1, title, info["url"], info["by"], info.get("date") or "?",
                                                              "yes" if free else "NO", "\n   REPEAT: featured in the week of %s" % repeat if repeat else ""))
        if info.get("image"):
            print("   image: " + info["image"])
        for p in info["problems"]:
            if p not in hard:
                print("   note: " + p)
        for p in style_notes(why):
            print("   why line: " + p)
        if not why:
            print("   why line: none given, so the card shows no 'why' text")
        if hard:
            failed.append("%s: %s" % (url, "; ".join(hard)))
        item = {"url": info["url"], "title": title, "by": info["by"], "why": why}
        if info.get("image"):
            item["image"] = info["image"]   # shown at the top of the card; linked from Substack, never copied
        items.append(item)
    if failed:
        print("\nREFUSED, nothing written:\n  " + "\n  ".join(failed))
        return 1
    if len(items) != 3:
        print("\nnote: %d picks given; the panel is designed for three." % len(items))
    archive = list(featured.get("archive", []))
    if featured.get("week_of") and featured["week_of"] != week.isoformat():
        archive = [dict({"url": x["url"], "title": x["title"], "by": x.get("by", ""), "week_of": featured["week_of"]},
                        **({"image": x["image"]} if x.get("image") else {})) for x in featured.get("items", [])] + archive
    out = {"week_of": week.isoformat()}
    intro = args.intro if args.intro is not None else featured.get("intro")
    if intro:
        out["intro"] = intro
        for p in style_notes(intro):
            print("intro: " + p)
    out["items"] = items
    out["archive"] = archive
    when = "%d %s %d" % (week.day, week.strftime("%B"), week.year)
    if args.dry_run:
        print("\nDry run: featured.json not written. It would read 'Week of %s' with %d picks and %d archived." % (when, len(items), len(archive)))
        return 0
    path = os.path.join(data, "featured.json")
    open(path, "w", encoding="utf8").write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("\nWrote %s: 'Week of %s', %d picks, %d earlier picks in the archive." % (os.path.relpath(path, ROOT), when, len(items), len(archive)))
    print("Next: python3 library/build.py, check the home page and Read, then publish.")
    return 0


def suggest(args):
    data = args.data
    featured = load(data, "featured.json", {})
    have = {clean_url(x["url"]) for x in load(data, "library.json", {}).get("entries", [])}
    seen = recent_urls(featured, next_monday() + timedelta(days=7))
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    found, errors = [], []
    for s in load(data, "substacks.json", []):
        base = s["url"].rstrip("/")
        cursor, pages = None, 0
        while pages < 8:   # a fortnight is one page for almost everyone; the cap stops a runaway
            pages += 1
            url = base + "/api/v1/archive?sort=new&limit=25" + ("&cursor=" + quote(cursor) if cursor else "")
            try:
                d = fetch(url, as_json=True)
            except (urllib.error.URLError, ValueError) as ex:
                errors.append("%s: %s" % (s["title"], ex))
                break
            posts = d.get("posts", []) if isinstance(d, dict) else d
            cursor = d.get("nextCursor") if isinstance(d, dict) else None
            older = False
            for p in posts:
                when = datetime.fromisoformat((p.get("post_date") or "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
                if when < since:
                    older = True
                    continue
                link = clean_url(p.get("canonical_url") or "%s/p/%s" % (base, p.get("slug", "")))
                if p.get("audience") != "everyone" or p.get("type") != "newsletter" or link in have or link in seen:
                    continue
                names = [b["name"] for b in p.get("publishedBylines") or [] if b.get("name")]
                found.append((when.date().isoformat(), s["title"], " and ".join(names) or s["by"], tidy(p.get("title")), link,
                              p.get("reaction_count") or 0, p.get("wordcount") or 0, tidy(p.get("subtitle") or p.get("description"))))
            if older or not cursor or not posts:
                break
    found.sort(reverse=True)
    print("Free articles from the last %d days, not in the library and not featured in the last %d weeks: %d\n" % (args.days, REPEAT_WEEKS, len(found)))
    for when, pub, who, title, link, likes, words, sub in found:
        print("%s  %s (%s)\n  %s\n  %s\n  %d likes, %d words%s\n" % (when, who, pub, title, link, likes, words, ("\n  " + sub[:160]) if sub else ""))
    if errors:
        print("Could not read %d Substacks:\n  %s" % (len(errors), "\n  ".join(errors)))
    print("Free means Substack marks the post 'everyone'. Load each pick before choosing it; setting the week checks again.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Set or suggest this week's three featured Substack articles.")
    ap.add_argument("urls", nargs="*", help="the addresses of this week's picks")
    ap.add_argument("--why", action="append", help="why it is worth reading, one per address, in order")
    ap.add_argument("--title", action="append", help="optional shorter card title, one per address ('' keeps Substack's)")
    ap.add_argument("--week", help="the Monday the picks are for, YYYY-MM-DD")
    ap.add_argument("--intro", help="optional line under the heading")
    ap.add_argument("--data", default=os.path.join(ROOT, "library", "data"), help="folder with featured.json, library.json, substacks.json")
    ap.add_argument("--dry-run", action="store_true", help="check and print, write nothing")
    ap.add_argument("--suggest", action="store_true", help="list recent free posts to choose from")
    ap.add_argument("--days", type=int, default=14, help="with --suggest, how far back to look (default 14)")
    args = ap.parse_args()
    if args.suggest:
        return suggest(args)
    if not args.urls:
        ap.error("give the addresses of the week's picks, or --suggest")
    return set_week(args)


if __name__ == "__main__":
    sys.exit(main())
