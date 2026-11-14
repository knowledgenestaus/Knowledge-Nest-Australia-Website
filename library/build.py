#!/usr/bin/env python3
"""Builds the Knowledge Nest Library pages.

Reads library/data/library.json and writes library*.html, library-search.json
and sitemap.xml into the site root. The page header, navigation and footer are
copied from about.html so the library always matches the rest of the site.

Run from the site root:  python3 library/build.py
"""
import html
import itertools
import json
import os
import re
from collections import OrderedDict, defaultdict
from datetime import date
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, "library", "data", "library.json"), encoding="utf8"))
SITE = "https://knowledgenest.com.au/"
EMAIL = "jo@knowledgenest.com.au"
SUGGEST = "mailto:%s?subject=Library%%20suggestion" % EMAIL

# Categories for filtering long lists, built from the focus areas.
TOPICS = OrderedDict([
    ("Explicit instruction", [2, 3, 4, 23, 24]),
    ("Cognitive science", [1, 3, 15]),
    ("English", [7, 8, 9, 10, 11]),
    ("Maths", [12]),
    ("Multi-tiered systems of support", []),   # split out of area 14 by keyword, below
    ("Inclusion and support", []),             # split out of area 14 by keyword, below
    ("Behaviour", [5, 20]),
    ("Instructional coaching", [16]),
    ("Change management and implementation", [17, 22]),
    ("Leadership and culture", [19, 21]),
    ("Curriculum", [6]),
    ("Assessment and data", [13]),
    ("Evidence and debates", [18]),
])
MTSS_WORDS = re.compile(r"mtss|multi-tiered|\btier|screen|intervention|progress monitoring|response to intervention", re.I)
INCLUSION_WORDS = re.compile(r"dyslexi|inclusi|special educational|\bsend\b|adaptive|diverse|twice|exceptional|teaching assistant|learning difficult|neurodiv|disabilit", re.I)


def topics_of(x):
    out = [t for t, ns in TOPICS.items() if set(ns) & set(x["areas"])]
    text = " ".join([x["title"], x.get("focus", ""), x.get("summary", "")])
    mtss = bool(MTSS_WORDS.search(text))
    incl = bool(INCLUSION_WORDS.search(text))
    if 14 in x["areas"] and not (mtss or incl):
        incl = True
    if mtss and (14 in x["areas"] or 13 in x["areas"] or re.search(r"mtss|multi-tiered", text, re.I)):
        out.append("Multi-tiered systems of support")
    if incl and (14 in x["areas"] or INCLUSION_WORDS.search(x["title"])):
        out.append("Inclusion and support")
    return [t for t in TOPICS if t in out]


# Shows featured at the top of the Listen page, in order.
TOP_SHOWS = ["Sold a Story", "Jones & McLean", "Chalk Dust", "Education Research Reading Room", "Mind the Gap: Making Education Work Across the Globe"]

# "Start here" on the library home. Each topic links to its areas and offers up to three picks,
# chosen by matching the start of a title; if a pick is missing, the first entry of that type is used.
START_HERE = [
    dict(title="Change management and implementation", areas=[17, 22],
         text="Whatever you want to improve, the first questions are the same. Where do you start, which goals do you set, and how do you lead people through the change?",
         picks=["A School's Guide to Implementation", "097 Implementation", "028 Reducing Change", "Building and operating an effective implementation team"]),
    dict(title="Explicit instruction", areas=[2, 4, 23],
         text="What a well-built lesson looks like, from the first explanation to independent practice, with every student taking part.",
         picks=["Explicit instruction: topic page", "060 Explicit Instruction", "Teach explicitly: Primary and secondary"]),
    dict(title="Structured literacy", areas=[7, 8, 9, 10],
         text="Phonics and fluency, comprehension and vocabulary, spelling and writing, taught systematically from Foundation to Year 6.",
         picks=["Science of Reading Presentation by Pamela Snow", "S7 E2 The Top 5 Ways", "029 How to Teach Students to Write"]),
    dict(title="Multi-tiered systems of support and inclusion", areas=[14],
         text="How strong whole-class teaching, early screening and targeted intervention fit together so every student gets the right support.",
         picks=["Leading MTSS", "S04E10", "S5 E17 MTSS for Reading"]),
    dict(title="Assessment and data", areas=[13, 4],
         text="Which assessments answer which questions, and how to use what they tell you without drowning in data.",
         picks=["027 Getting Assessment Right", "S03E04", "Using data in MTSS: Screening"]),
]

AREAS = sorted(DATA["areas"], key=lambda a: a["n"])
AREA = {a["n"]: a for a in AREAS}
ENTRIES = DATA["entries"]

def _load(name, default):
    path = os.path.join(ROOT, "library", "data", name)
    return json.load(open(path, encoding="utf8")) if os.path.exists(path) else default

# Learn: webinars and longer professional learning. Some entries move across from Watch; others are listed in learn.json.
LEARN = _load("learn.json", {"move": [], "entries": []})
for x in ENTRIES:
    if x["type"] == "watch" and x["title"] in LEARN["move"]:
        x["type"] = "learn"
for x in LEARN["entries"]:
    ENTRIES.append(dict(x, type="learn"))
SUBSTACKS = _load("substacks.json", [])
THUMBS = _load("thumbs.json", {})  # video url -> preview image url (linked, never copied); see tools/thumbs.py
# Jo's must-follow Substacks, by title, shown first on the Read page. Leave empty until chosen.
MUST_SUBSTACKS = []
SHOWS = DATA["shows"]
SHOW_ART = {s["title"]: s["art"] for s in SHOWS if s.get("art")}  # cover art by show, for episode cards
# Preview images that are video stills (shown edge to edge); anything else is shown whole, like a logo.
STILL_HOSTS = ("ytimg.com", "edresearch.edu.au", "vimeocdn.com", "boltdns.net")
VTLM = DATA["vtlm"]

TYPES = OrderedDict([
    ("watch", dict(label="Watch", page="library-watch.html", title="Watch: classroom videos", tile="Watch", noun="videos",
                   blurb="Classroom footage, demonstrations and explainers showing practice in action.")),
    ("learn", dict(label="Learn", page="library-learn.html", title="Learn: webinars and longer sessions", tile="Learn", noun="sessions",
                   blurb="Webinars and longer sessions to sit down with, alone or as a staff.")),
    ("listen", dict(label="Listen", page="library-listen.html", title="Listen: podcasts", tile="Listen", noun="episodes",
                    blurb="Must-listen shows, and episodes sorted by category.")),
    ("read", dict(label="Read", page="library-read.html", title="Read: articles, blogs and Substacks", tile="Read", noun="articles and guides",
                  blurb="Short reads, practice guides and Substacks worth following.")),
    ("research", dict(label="Research", page="library-research.html", title="Research: papers and reviews", tile="Research", noun="papers and reviews",
                      blurb="Foundational papers, reviews and meta-analyses.")),
    ("voice", dict(label="Voices", page="library-voices.html", title="Voices: People and organisations to follow", tile="Voices", noun="people and organisations to follow",
                   blurb="The researchers, teachers, writers and organisations worth your time.")),
    ("curriculum", dict(label="Curriculum", page="library-curriculum.html", title="Curriculum: free lesson materials", tile="Curriculum", noun="collections",
                        blurb="Openly available lesson materials, scope and sequences.")),
])


def illo(key, cls="kn-illo", size=320):
    """A bespoke illustration, if one has been added at assets/illo/<key>.webp. Returns '' when it has not."""
    if os.path.exists(os.path.join(ROOT, "assets", "illo", key + ".webp")):
        return '<img class="%s" src="assets/illo/%s.webp" alt="" width="%d" height="%d" loading="lazy" decoding="async">' % (cls, key, size, size)
    return ""

# Domains as shown on the site. These regroup the areas from the catalogue by area number.
DOMAIN_OF = {
    "Literacy": [7, 8, 9, 10, 11],
    "Numeracy": [12],
    "Knowledge-rich curriculum": [6],
    "MTSS and assessment": [13, 14],
    "Research and evidence": [18],
}
for a in AREAS:
    for name, ns in DOMAIN_OF.items():
        if a["n"] in ns:
            a["domain"] = name
DOMAIN_ORDER = ["How learning works", "Teaching practice", "Literacy", "Numeracy", "Knowledge-rich curriculum", "MTSS and assessment",
                "Coaching and professional learning", "Leadership and culture", "Implementation and change", "Research and evidence"]
assert all(a["domain"] in DOMAIN_ORDER for a in AREAS)

# ---------- house style for colons ----------
# 1. The word after a colon starts with a capital ("Watch: Classroom videos"). Applied to every piece of visible
#    text as it is written out, so the data files stay as they are and new entries follow the rule automatically.
# 2. In titles and headings the part up to the colon is the bold "lead-in" and the rest is lighter.
#    Set LEAD_IN = False to switch that off in the generated pages (or see the .lead-in rules in styles.css).
LEAD_IN = True
# Words that keep their small first letter after a colon. Words with a capital inside them (researchED, iPad,
# eBook, mRNA, pH) and web or email addresses are left alone automatically; list anything else here.
KEEP_LOWER = ("e.g.", "i.e.", "eg.", "ie.", "etc.", "researchED", "iPad", "iPhone", "iOS", "eBook", "eBooks",
              "eSafety", "eLearning", "edX", "pH", "mRNA", "macOS")
_COLON = re.compile(r"(:[ \u00a0]+[\"'\u2018\u201c(\[]?)([a-z])([^\s<]*)")
CAP_CHANGED = set()   # texts the rule changed in this build, for the report line at the end


def _cap(m):
    lead, first, rest = m.groups()
    word = (first + rest).rstrip(".,;:!?)\"'\u2019\u201d")
    tail = m.string[m.start(2):]
    if (any(tail.startswith(k) and not tail[len(k):len(k) + 1].isalnum() for k in KEEP_LOWER)  # a listed term
            or re.match(r"[a-z]+[A-Z]", word)                # a capital inside the word: researchED, iPad, pH
            or re.match(r"[a-z]\.[a-z]\.", first + rest)       # e.g., i.e., a.m.
            or re.search(r"[a-z0-9]\.[a-z]{2,}|@|//", word)): # a web or email address
        return m.group(0)
    return lead + first.upper() + rest


def cap_after_colon(text):
    """Capitalises the word after a colon and a space: "Watch: classroom videos" -> "Watch: Classroom videos".
    Left alone: times and ratios (9:30, 4.5:1), web addresses, a colon with no space or no letter after it,
    a colon at the end of a line, and the deliberately lower-case terms described above KEEP_LOWER."""
    if not text or ":" not in text:
        return text
    out = _COLON.sub(_cap, text)
    if out != text:
        CAP_CHANGED.add(text)
    return out


def e(text):
    """Visible text: colon rule applied, then escaped for HTML."""
    return html.escape(cap_after_colon(text))


ea = html.escape   # web addresses and machine-read attribute values: escaped only, never re-cased


def title_html(text):
    """A title or heading, escaped, with any lead-in before the first colon marked up:
    <span class="lead-in">Watch:</span><span class="lead-rest"> Classroom videos</span>.
    Only for titles, headings and labels. Never for summaries, meta text, the search index or attributes."""
    text = cap_after_colon(text)
    m = re.match(r"(.*?[^\s:]:)(\s+\S.*)$", text, flags=re.S) if LEAD_IN else None
    if not m:
        return html.escape(text)
    # A lone "A", "An" or "The" must not be left hanging at the end of the bold line, so it is joined to the next word.
    rest = re.sub(r"^(\s+(?:A|An|The))\s", "\\1&nbsp;", html.escape(m.group(2)))
    return '<span class="lead-in">%s</span><span class="lead-rest">%s</span>' % (html.escape(m.group(1)), rest)


def label_html(text):
    """A short label that ends in a colon, such as "Popular:"."""
    return '<span class="lead-in">%s</span>' % html.escape(text)


NEWTAB = '<span class="sr-only"> (opens in a new tab)</span>'
ARROW = '<span aria-hidden="true">&rarr;</span>'


def area_page(a):
    return "library-%s.html" % a["slug"]


def public(name):
    """The address visitors and search engines see for a page file. The host serves pages without ".html" and the
    home page as "/", so canonical links, share addresses, structured data and the sitemap use that form.
    Links inside the pages keep their file names."""
    if name in ("", "index.html"):
        return SITE
    return SITE + (name[:-5] if name.endswith(".html") else name)


def domain_of(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def by_area(entries):
    out = defaultdict(list)
    for x in entries:
        for n in x["areas"]:
            out[n].append(x)
    return out


def short_area(n):
    return AREA[n]["name"].split(":")[0]


def source_of(x):
    """Who to file an entry under in the Source filter. A Learn session by 'Host, with Presenter' is filed under the host."""
    return x["by"].split(", with ")[0] if x["type"] == "learn" else x["by"]


def access_of(x):
    return next((t for t in ("Free account needed", "Check cost") if t in x["tags"]), "Free")


def shown_meta(x):
    """The details line of a card: empty items and a literal "None" from the sheet are dropped. A Learn session
    with no running time falls back to its length band, so every session says roughly how long it is."""
    meta = [m for m in x["meta"] if m and m.strip() and m.strip().lower() != "none"]
    if x["type"] == "learn" and x.get("length") and not any(re.search(r"minute|hour|session|animation|\d:\d\d", m, re.I) for m in meta):
        meta = [x["length"]] + meta
    return meta


def shown_tags(x):
    """Tags, without one that only repeats the details line ("Foundational research" and a "Foundational" tag)."""
    return [t for t in x["tags"] if not any(m.lower().startswith(t.lower()) for m in x["meta"])]


def card(x, show_type=True, level="h3", filterable=False):
    t = TYPES[x["type"]]
    bits = [e(m) for m in shown_meta(x)]
    by = e(x["by"]) if x["by"] else ""
    line = " &middot; ".join([b for b in [by] + bits if b])
    tags = "".join('<span class="lib-tag%s">%s</span>' % (" lib-tag-free" if tg.lower().startswith("free") and tg != "Free account needed" else "", e(tg)) for tg in shown_tags(x))
    badge = '<span class="lib-type lib-type-%s">%s</span>' % (x["type"], t["label"]) if show_type else ""
    focus = '<p class="lib-focus">%s</p>' % e(x["focus"]) if x.get("focus") else ""
    summary = '<p class="lib-summary">%s</p>' % e(x["summary"]) if x.get("summary") else ""
    topics = ""
    data = ""
    if filterable:
        topics = '<p class="lib-topics">%s</p>' % "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(short_area(n))) for n in x["areas"]) if x["areas"] else ""
        text = " ".join([x["title"], x["by"], x.get("summary", ""), x.get("focus", ""), " ".join(x["meta"])] + [AREA[n]["name"] for n in x["areas"]]).lower()
        data = ' data-topics="%s" data-areas="%s" data-bands="%s" data-subject="%s" data-region="%s" data-by="%s" data-text="%s"' % (
            ea("|".join(topics_of(x))), ",".join(str(n) for n in x["areas"]), ",".join(x.get("bands", [])), ea(x.get("subject", "")), ea(x.get("region", "")), ea(source_of(x)), ea(text))
        if x["type"] == "learn":
            data += ' data-length="%s" data-audience="%s" data-access="%s"' % (ea(x.get("length", "")), ea(x.get("audience", "")), ea(access_of(x)))
    thumb = ""
    if x["type"] in ("watch", "learn"):
        img = THUMBS.get(x["url"])
        pic = ('<img src="%s" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="480" height="270" '
               'onerror="this.remove()">' % ea(img)) if img else ""
        kind = "" if not img else (" lib-thumb-still" if any(h in img for h in STILL_HOSTS) else " lib-thumb-logo")
        thumb = ('<a class="lib-thumb%s" href="%s" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">'
                 '<span class="lib-thumb-name">%s</span>%s<span class="lib-thumb-play"></span></a>' % (kind, ea(x["url"]), e(x["by"] or domain_of(x["url"])), pic))
    head = '%s%s<%s class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></%s>%s' % (
        badge, focus, level, ea(x["url"]), title_html(x["title"]), NEWTAB, level, ('<p class="lib-by">%s</p>' % line) if line else "")
    # A small picture beside the heading: the show's cover art on episodes, the page's own preview image on reading.
    # Linked from the creator's server, never copied; if it fails to load it is removed and the card reads as plain text.
    side = SHOW_ART.get(x["by"]) if x["type"] == "listen" else (THUMBS.get(x["url"]) if x["type"] in ("read", "research", "curriculum") else None)
    if side:
        w, h = (56, 56) if x["type"] == "listen" else (64, 64)
        head = ('<div class="lib-card-head"><img class="lib-card-pic%s" src="%s" alt="" width="%d" height="%d" loading="lazy" decoding="async" '
                'referrerpolicy="no-referrer" onerror="this.remove()"><div>%s</div></div>' % (" lib-card-art" if x["type"] == "listen" else " lib-card-side", ea(side), w, h, head))
    return (
        '<article class="lib-card%s" data-type="%s"%s>%s%s'
        '%s%s<p class="lib-card-foot">%s<span class="lib-source">Opens at %s</span></p></article>'
        % (" has-thumb" if thumb else "", x["type"], data, thumb, head, summary, topics, tags, e(domain_of(x["url"])))
    )


MIX_TYPES = ("watch", "learn", "listen")
_SERIES = re.compile(r"^(.*?)[,:]?\s+(?:episode|part|session)\s+\d+", re.I)


def mix(entries):
    """Spread sources through a list so one creator never fills a run of cards.
    Entries from the same source keep their original order. Numbered parts of one series
    (episode 1, 2, 3 ...) stay together, in order, as a single block."""
    units, index = [], {}
    for x in entries:
        m = _SERIES.match(x["title"])
        key = (x["by"], m.group(1).lower()) if m else None
        if key and key in index:
            units[index[key]].append(x)
        else:
            if key:
                index[key] = len(units)
            units.append([x])
    by_src = {}
    for i, u in enumerate(units):
        by_src.setdefault(u[0]["by"], []).append((i, u))
    # Place each source's cards at even intervals through the list, in proportion to how many it has.
    placed = []
    for src, us in by_src.items():
        for k, (i, u) in enumerate(us):
            placed.append(((k + 0.5) / len(us), us[0][0], i, u))
    placed.sort(key=lambda t: t[:3])
    out = [u for *_, u in placed]
    # Where two cards from one source still touch, swap the second with the next card from elsewhere.
    for a in range(1, len(out)):
        if out[a][0]["by"] == out[a - 1][0]["by"]:
            for c in range(a + 1, len(out)):
                if out[c][0]["by"] != out[a][0]["by"] and (c + 1 == len(out) or out[c + 1][0]["by"] != out[a][0]["by"]):
                    out[a], out[c] = out[c], out[a]
                    break
    # Do not open with the largest source when there is another to lead with.
    if len(by_src) > 1 and len(out) > 2:
        biggest = max(by_src, key=lambda k: len(by_src[k]))
        if out[0][0]["by"] == biggest and len(by_src[biggest]) > 1 and out[1][0]["by"] != out[2][0]["by"]:
            out[0], out[1] = out[1], out[0]
    return [x for u in out for x in u]


def cards(entries, show_type=True, level="h3", filterable=False, mixed=True):
    entries = list(entries)
    if mixed and entries and all(x["type"] in MIX_TYPES for x in entries):
        entries = mix(entries)
    return '<div class="lib-grid">%s</div>' % "".join(card(x, show_type, level, filterable) for x in entries)


def options(values, all_label):
    return '<option value="">%s</option>%s' % (e(all_label), "".join('<option value="%s">%s</option>' % (ea(v), e(l)) for v, l in values))


def filter_bar(items, kind):
    """Filter controls for a long list. Works without JavaScript as a plain list."""
    area_ns = [a["n"] for d in DOMAIN_ORDER for a in AREAS if a["domain"] == d and any(a["n"] in x["areas"] for x in items)]
    topic_names = [t for t in TOPICS if any(t in topics_of(x) for x in items)]
    fields = ['<div class="lib-field"><label for="fTopic">Category</label><select id="fTopic" data-filter="topics">%s</select></div>'
              % options([(t, t) for t in topic_names], "All categories")]
    fields += ['<div class="lib-field"><label for="fArea">Focus area</label><select id="fArea" data-filter="areas">%s</select></div>'
              % options([(str(n), short_area(n)) for n in area_ns], "All focus areas")]
    if kind == "watch":
        fields.append('<div class="lib-field"><label for="fBand">Year level</label><select id="fBand" data-filter="bands">%s</select></div>'
                      % options([("F-2", "Foundation to Year 2"), ("3-6", "Years 3 to 6"), ("Secondary", "Secondary")], "All year levels"))
        subjects = [v for v in ["Literacy and English", "Maths", "Across subjects", "Other subjects"] if any(x.get("subject") == v for x in items)]
        fields.append('<div class="lib-field"><label for="fSubject">Subject</label><select id="fSubject" data-filter="subject">%s</select></div>'
                      % options([(v, v) for v in subjects], "All subjects"))
        regions = sorted(set(x.get("region") for x in items if x.get("region")))
        fields.append('<div class="lib-field"><label for="fRegion">Where it was filmed</label><select id="fRegion" data-filter="region">%s</select></div>'
                      % options([(v, v) for v in regions], "Anywhere"))
    if kind == "learn":
        lengths = [v for v in ["Under 30 minutes", "30 to 60 minutes", "Over 60 minutes", "Series"] if any(x.get("length") == v for x in items)]
        fields.append('<div class="lib-field"><label for="fLength">Length</label><select id="fLength" data-filter="length">%s</select></div>'
                      % options([(v, v) for v in lengths], "Any length"))
        audiences = sorted(set(x.get("audience") for x in items if x.get("audience")))
        fields.append('<div class="lib-field"><label for="fAudience">Made for</label><select id="fAudience" data-filter="audience">%s</select></div>'
                      % options([(v, v) for v in audiences], "Everyone"))
        regions = sorted(set(x.get("region") for x in items if x.get("region")))
        fields.append('<div class="lib-field"><label for="fRegion">Where the presenter is from</label><select id="fRegion" data-filter="region">%s</select></div>'
                      % options([(v, v) for v in regions], "Anywhere"))
        access = [v for v in ["Free", "Free account needed", "Check cost"] if any(access_of(x) == v for x in items)]
        fields.append('<div class="lib-field"><label for="fAccess">Access</label><select id="fAccess" data-filter="access">%s</select></div>'
                      % options([(v, v) for v in access], "Any"))
    by_label = "Show" if kind == "listen" else "Source"
    sources = sorted(set(source_of(x) for x in items if x["by"]), key=str.lower)
    fields.append('<div class="lib-field"><label for="fBy">%s</label><select id="fBy" data-filter="by">%s</select></div>'
                  % (by_label, options([(v, v) for v in sources], "All %ss" % by_label.lower())))
    fields.append('<div class="lib-field lib-field-wide"><label for="fText">Search within this page</label>'
                  '<input type="search" id="fText" placeholder="e.g. worked examples" autocomplete="off"></div>')
    chips = "".join('<button type="button" class="lib-chip" data-topic="%s">%s <span>%d</span></button>'
                    % (ea(t), e(t), sum(1 for x in items if t in topics_of(x))) for t in topic_names)
    return ('<button type="button" class="lib-filter-toggle" id="libFilterToggle" aria-expanded="false" aria-controls="libFilters">Filter this list</button>'
            + '<div class="lib-chips" id="libChips"><p>Browse by category</p><div>%s</div></div>' % chips +
            '<form class="lib-filters" id="libFilters"><div class="lib-filter-row">%s</div>'
            '<p class="lib-filter-status"><span id="fCount" role="status" aria-live="polite"></span> '
            '<button type="reset" class="lib-reset">Clear filters</button></p></form>' % "".join(fields))


def filtered_list(items, kind):
    order = {a["n"]: i for i, a in enumerate(sorted(AREAS, key=lambda a: (DOMAIN_ORDER.index(a["domain"]), a["n"])))}
    area_rank = lambda x: (order.get(x["areas"][0], 99) if x["areas"] else 99)
    lead = {}  # a numbered series sits where its first part belongs, so its parts stay together
    for x in items:
        m = _SERIES.match(x["title"])
        if m:
            lead.setdefault((x["by"], m.group(1).lower()), area_rank(x))
    def rank(x):
        m = _SERIES.match(x["title"])
        return lead[(x["by"], m.group(1).lower())] if m else area_rank(x)
    items = sorted(items, key=rank)
    # Within each area of practice, spread the sources so no single creator dominates a stretch of the page.
    items = [x for _, run in itertools.groupby(items, key=rank) for x in mix(list(run))]
    return (filter_bar(items, kind) + '<div id="libList">%s</div>' % cards(items, False, "h3", True, mixed=False)
            + '<p class="lib-more" hidden><button type="button" class="btn btn-primary" id="libMore">Show more</button></p>'
            + '<p class="lib-empty" id="libEmpty" hidden>Nothing matches those filters yet. Try clearing one, or <a href="%s">email a suggestion</a>. '
            '<button type="reset" form="libFilters" class="lib-reset">Clear filters</button></p>' % SUGGEST
            + '<script src="library/filter.js?v=5" defer></script>')


def hero(tagline, h1, lead, crumbs=None, extra="", art=None):
    crumb = ""
    if crumbs:
        parts = ['<a href="%s">%s</a>' % (h, e(l)) if h else '<span aria-current="page">%s</span>' % e(l) for l, h in crumbs]
        crumb = '<nav class="lib-crumbs" aria-label="Breadcrumb">%s</nav>' % " <span aria-hidden=\"true\">/</span> ".join(parts)
    pic = illo(art, "page-hero-illo", 360) if art else ""
    return ('<section class="page-hero lib-hero%s"><div class="container page-hero-inner"><div class="page-hero-text lib-hero-text">%s'
            '<p class="hero-tagline">%s</p><h1>%s</h1><p class="page-hero-lead">%s</p>%s</div>%s</div></section>'
            % (" has-illo" if pic else "", crumb, e(tagline), title_html(h1), lead, extra, pic))


def start_here(limit=None):
    cards_html = []
    for t in (START_HERE[:limit] if limit else START_HERE):
        pool = [x for x in ENTRIES if set(x["areas"]) & set(t["areas"])]
        picks = []
        for p in t["picks"]:
            hit = next((x for x in ENTRIES if cap_after_colon(x["title"]).startswith(cap_after_colon(p))), None)
            if hit and hit not in picks:
                picks.append(hit)
        for typ in ("read", "listen", "watch"):
            if len(picks) >= 3:
                break
            if not any(x["type"] == typ for x in picks):
                extra = next((x for x in pool if x["type"] == typ and x not in picks), None)
                if extra:
                    picks.append(extra)
        lis = "".join('<li><span class="lib-type lib-type-%s">%s</span> <a href="%s" target="_blank" rel="noopener">%s%s</a></li>'
                      % (x["type"], TYPES[x["type"]]["label"], ea(x["url"]), e(x["title"]), NEWTAB) for x in picks[:3])  # a link list, so no bold lead-in
        links = "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(short_area(n))) for n in t["areas"])
        cards_html.append('<article class="lib-start"><p class="lib-start-n" aria-hidden="true">%02d</p><h3>%s</h3><p>%s</p><p class="lib-start-label">Three to begin with</p><ul>%s</ul>'
                          '<p class="lib-start-label">See everything on</p><p class="lib-topics">%s</p></article>' % (len(cards_html) + 1, title_html(t["title"]), e(t["text"]), lis, links))
    return ('<section class="section" id="start"><div class="container"><div class="section-header section-header-illo">ILLO_START<div><p class="kn-eyebrow">Not sure where to begin?</p><h2>Start here</h2>'
            '<p>%s good places to begin a school\'s professional learning.</p></div></div>'
            '<div class="lib-starts%s">%s</div>%s</div></section>' % (
                "Three" if limit == 3 else "Five", " lib-starts-three" if limit == 3 else "", "".join(cards_html),
                '<p class="lib-starts-more"><a href="library.html#start">See all five starting points %s</a></p>' % ARROW if limit else "")).replace("ILLO_START", illo("start", "section-illo", 200))


def credit_panels():
    return ('<section class="section lib-about"><div class="container"><div class="lib-panels">'
            '<div class="lib-panel"><p class="lib-eyebrow">About this collection</p>'
            "<h2>Other people's brilliant work, gathered in one place</h2>"
            "<p>I'm Jo Griffin. I was spending a long time trawling the internet to find resources that support teachers' professional learning, "
            "and thought it might help others if they were all in one place, sorted into categories.</p>"
            "<p>This is a collection, not my own work. Every resource belongs to the people who created it. Each entry names its creator "
            "and links straight to the original, and nothing is copied or hosted here.</p>"
            '<p class="lib-small">Is your work listed here? If you would like it described differently or removed, just '
            '<a href="mailto:%s?subject=Library%%20listing">let me know</a>.</p></div>'
            '<div class="lib-panel lib-panel-grow">ILLO_SUGGEST<p class="lib-eyebrow">Help it grow</p><h2>Know something that belongs here?</h2>'
            "<p>This library is built by sharing. If there is a video, podcast, article or piece of research that has helped you or your team, "
            "send a quick email with the link and it can be added for everyone.</p>"
            '<p><a href="%s" class="btn btn-accent">Email a suggestion</a></p></div></div></div></section>' % (EMAIL, SUGGEST)).replace("ILLO_SUGGEST", illo("suggest", "lib-panel-illo", 220))


def suggest_box():
    return ('<div class="lib-side-box">ILLO_SUGGEST<h2>Something missing?</h2><p>This library is built by sharing. Send a quick email with a link and it can be added for everyone.</p>'
            '<p><a href="%s" class="btn btn-outline btn-sm">Email a suggestion</a></p></div>' % SUGGEST).replace("ILLO_SUGGEST", illo("suggest", "lib-side-illo", 160))


# ---------- page shell, copied from about.html ----------
def shell():
    src = open(os.path.join(ROOT, "about.html"), encoding="utf8").read()
    head = src[:src.index("<main")]
    tail = src[src.index("</main>"):]
    head = head.replace(' class="active" aria-current="page"', "")
    head = head.replace('<a href="library.html">Library</a>', '<a href="library.html" class="active" aria-current="page">Library</a>', 1)
    head = re.sub(r'<script type="application/ld\+json">.*?</script>', "@@LD@@", head, flags=re.S)
    return head, tail


HEAD, TAIL = shell()
BUILT = []


def write(name, title, desc, body, crumb_name=None):
    head = HEAD
    head = re.sub(r"<title>.*?</title>", "<title>%s</title>" % e(title), head, flags=re.S)
    head = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + e(desc), head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + e(desc), head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + e(title), head)
    head = re.sub(r'(<meta name="twitter:description" content=")[^"]*', lambda m: m.group(1) + e(desc), head)
    head = re.sub(r'(<meta name="twitter:title" content=")[^"]*', lambda m: m.group(1) + e(title), head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*', lambda m: m.group(1) + public(name), head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + public(name), head)
    items = [("Home", SITE), ("Library", public("library.html"))]
    if crumb_name:
        items.append((crumb_name, public(name)))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": cap_after_colon(n), "item": u} for i, (n, u) in enumerate(items)]}
    head = head.replace("@@LD@@", '<script type="application/ld+json">\n%s\n  </script>' % json.dumps(ld, indent=2))
    page = head + '<main id="main-content" tabindex="-1">\n' + body + "\n" + TAIL
    open(os.path.join(ROOT, name), "w", encoding="utf8").write(page)
    BUILT.append(name)


def count(t):
    return sum(1 for x in ENTRIES if x["type"] == t)


def tile(href, key, title, blurb, n, noun):
    pic = illo(key, "kn-tile-illo", 240)
    art = pic or '<span class="kn-tile-num" aria-hidden="true">%d</span>' % n
    return ('<a href="%s" class="kn-tile kn-tile-%s%s"><span class="kn-tile-art">%s</span><span class="kn-tile-body">'
            '<span class="kn-tile-title">%s</span><span class="kn-tile-text">%s</span>'
            '<span class="kn-tile-cta">%d %s %s</span></span></a>' % (href, key, " kn-tile-pic" if pic else "", art, title_html(title), e(blurb), n, e(noun), ARROW))


def type_tiles():
    out = [tile(t["page"], key, t["tile"], t["blurb"], count(key), t["noun"]) for key, t in TYPES.items()]
    used = set(n for x in ENTRIES for n in x["areas"])
    n_areas = len([d for d in DOMAIN_ORDER if any(a["domain"] == d and a["n"] in used for a in AREAS)])
    out.append(tile("library.html#areas", "areas", "By area of practice", "Ten nests of knowledge, from how learning works to leading change.", n_areas, "areas"))
    return '<div class="kn-tiles">%s</div>' % "".join(out)


DOMAIN_ABOUT = {
    "How learning works": "Memory, attention and motivation, and what they mean for teaching.",
    "Teaching practice": "Explicit instruction, retrieval, checking for understanding, routines and feedback.",
    "Literacy": "Phonics and fluency, comprehension, spelling, writing and oral language.",
    "Numeracy": "Clear, evidence-informed mathematics teaching from the early years up.",
    "Knowledge-rich curriculum": "Sequencing knowledge so learning builds, within and across subjects.",
    "MTSS and assessment": "Screening, assessment and progress monitoring, with support at Tier 1, 2 and 3.",
    "Coaching and professional learning": "Instructional coaching and professional learning that changes practice.",
    "Leadership and culture": "Instructional leadership, school culture, behaviour and strong teams.",
    "Implementation and change": "Putting good ideas into practice, and bringing people with you.",
    "Research and evidence": "Reading the evidence, weighing the debates and spotting the myths.",
}


# What a domain covers, shown as chips on its page. These are elements of understanding, not separate pages.
DOMAIN_ELEMENTS = {
    "MTSS and assessment": ["Tier 1: strong teaching for all", "Tier 2: targeted support", "Tier 3: intensive support",
                            "Screening", "Progress monitoring", "Assessment and data"],
}


def domain_slug(d):
    return re.sub(r"[^a-z0-9]+", "-", d.lower()).strip("-")


def domain_areas(d, counts):
    return [a for a in AREAS if a["domain"] == d and counts.get(a["n"], 0)]


def domain_page(d, counts):
    """A domain with one area goes straight to that area; otherwise to its own page."""
    areas = domain_areas(d, counts)
    return area_page(areas[0]) if len(areas) == 1 else "library-domain-%s.html" % domain_slug(d)


def area_index(counts):
    cols = []
    for d in DOMAIN_ORDER:
        areas = domain_areas(d, counts)
        if not areas:
            continue
        n = len(set(x["url"] for x in ENTRIES if set(x["areas"]) & set(a["n"] for a in areas)))
        pic = illo("domain-" + domain_slug(d), "lib-domain-illo", 200)
        cols.append('<a class="lib-domain" href="%s">%s<span class="lib-domain-title">%s</span><span class="lib-domain-text">%s</span>'
                    '<span class="kn-tile-cta">%d resources %s</span></a>' % (domain_page(d, counts), pic, title_html(d), e(DOMAIN_ABOUT.get(d, "")), n, ARROW))
    return '<div class="lib-domains">%s</div>' % "".join(cols)


def build_domains():
    counts = {n: len(v) for n, v in by_area(ENTRIES).items()}
    for d in DOMAIN_ORDER:
        areas = domain_areas(d, counts)
        if len(areas) < 2:
            continue
        body = hero("Browse by area", d, e(DOMAIN_ABOUT.get(d, "")), crumbs=[("Library", "library.html"), ("Areas", "library.html#areas"), (d, None)], art="domain-" + domain_slug(d),
                    extra=('<p class="lib-practices">%s%s</p>' % (label_html("What this covers:"), "".join("<em>%s</em>" % e(x) for x in DOMAIN_ELEMENTS[d]))) if d in DOMAIN_ELEMENTS else "")
        tiles = "".join('<a class="lib-strand" href="%s"><span class="lib-domain-title">%s</span><span class="lib-domain-text">%s</span>'
                        '<span class="kn-tile-cta">%d resources %s</span></a>' % (area_page(a), title_html(a["name"]), e(a["about"]), counts[a["n"]], ARROW) for a in areas)
        body += ('<section class="section"><div class="container"><div class="section-header"><h2>%d areas in %s</h2>'
                 '<p>Each one gathers videos, podcasts, reading and research in one place.</p></div><div class="lib-strands">%s</div></div></section>' % (len(areas), e(d), tiles))
        body += credit_panels()
        write("library-domain-%s.html" % domain_slug(d), "%s | The Knowledge Nest Library" % d,
              "%s: free professional learning resources for teachers and leaders. %s" % (d, DOMAIN_ABOUT.get(d, "")), body)


def jump(pairs):
    return '<p class="page-hero-jump">%s</p>' % "".join('<a href="#%s">%s</a>' % (i, e(l)) for i, l in pairs)


# ---------- library home ----------
def build_home():
    counts = {n: len(v) for n, v in by_area(ENTRIES).items()}
    popular = [2, 7, 10, 16, 17, 4]
    chips = "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(AREA[n]["name"].split(":")[0].split(",")[0])) for n in popular)
    search = ('<form class="lib-search" role="search" id="libSearch" action="library" method="get">'
              '<label for="q" class="sr-only">Search the library</label>'
              '<input type="search" id="q" name="q" placeholder="Search by topic, practice or person, e.g. hinge questions" autocomplete="off" maxlength="100">'
              '<button type="submit" class="btn btn-primary">Search</button></form>'
              '<p class="page-hero-jump lib-popular">%s%s</p>' % (label_html("Popular:"), chips))
    lead = ("Great professional learning resources are scattered all over the internet. This library gathers the best of other people's work "
            "in one place, sorted by topic, so you can spend your time learning instead of searching.")
    body = hero("A curated collection, free for teachers and leaders", "The Knowledge Nest Library", lead, extra=search, art="home")
    body += ('<section class="section lib-results-section" id="results" hidden><div class="container">'
             '<h2 id="resultsHeading" tabindex="-1">Search results</h2><p class="lib-results-note" id="resultsNote" role="status" aria-live="polite"></p>'
             '<div id="resultsList"></div><p><button type="button" class="btn btn-primary btn-sm" id="clearSearch">Clear search</button></p></div></section>')
    body += ('<section class="section" id="types"><div class="container"><div class="section-header"><p class="kn-eyebrow">%d resources, free to browse</p><h2>Browse the library</h2>'
             '<p>Know how you want to learn today? Pick a shelf. Almost everything is free, and anything that may cost money is marked "Check cost".</p></div>%s</div></section>' % (len(ENTRIES), type_tiles()))
    body += start_here().replace('<section class="section" id="start">', '<section class="section section-tint" id="start">')
    body += ('<section class="section" id="areas"><div class="container"><div class="section-header"><h2>Browse by area</h2>'
             '<p>Every area gathers videos, podcasts, reading and research in one place.</p></div>%s</div></section>'
             % area_index(counts))
    elements = "".join('<span>%s</span>' % e(k) for frame in VTLM for k in VTLM[frame] if frame.startswith("VTLM"))
    body += ('<section class="section section-tint"><div class="container"><div class="lib-band"><div class="lib-band-text"><p class="lib-eyebrow">For Victorian schools</p>'
             '<h2>Browse by the Victorian Teaching and Learning Model 2.0</h2>'
             '<p>Podcast episodes matched to each element of learning and teaching, and to current Victorian priorities.</p>'
             '<p><a href="library-vtlm.html" class="btn btn-accent">Open podcasts by the VTLM 2.0</a></p></div>'
             '<div class="lib-band-chips">%s</div></div>'
             '<p class="lib-own">Looking for my own articles and a downloadable guide? <a href="resources.html">Find them here</a>.</p>'
             '</div></section>' % elements)
    body += credit_panels()
    body += '<script src="library/search.js?v=6" defer></script>'
    write("library.html", "The Knowledge Nest Library | Free Professional Learning Resources",
          "A free, curated library of videos, podcasts, blogs, research and curriculum materials to support your school's professional learning journey.",
          body)


# ---------- type pages ----------
def domain_sections(entries, show_type=False):
    """Entries grouped under the domain of their first area. Used where a shelf is too small to fill a heading per area."""
    counts = {n: len(v) for n, v in by_area(ENTRIES).items()}
    groups = defaultdict(list)
    for x in entries:
        groups[AREA[x["areas"][0]]["domain"] if x["areas"] else ""].append(x)
    nav, out = [], []
    for d in DOMAIN_ORDER:
        if groups.get(d):
            nav.append(("d-" + domain_slug(d), d))
            out.append('<section class="lib-group" id="d-%s"><h2><a href="%s">%s</a> <span class="lib-count">%d</span></h2>%s</section>'
                       % (domain_slug(d), domain_page(d, counts), title_html(d), len(groups[d]), cards(groups[d], show_type)))
    if groups.get(""):
        nav.append(("more", "More"))
        out.append('<section class="lib-group" id="more"><h2>More <span class="lib-count">%d</span></h2>%s</section>' % (len(groups[""]), cards(groups[""], show_type)))
    return nav, "".join(out)


def grouped_sections(entries, show_type=False):
    """Entries grouped under their first area, in framework order."""
    groups = defaultdict(list)
    for x in entries:
        groups[x["areas"][0] if x["areas"] else 0].append(x)
    order = [a["n"] for d in DOMAIN_ORDER for a in AREAS if a["domain"] == d and groups.get(a["n"])]
    nav = [("a%d" % n, AREA[n]["name"].split(":")[0]) for n in order]
    out = []
    for n in order:
        out.append('<section class="lib-group" id="a%d"><h2><a href="%s">%s</a> <span class="lib-count">%d</span></h2>%s</section>'
                   % (n, area_page(AREA[n]), title_html(AREA[n]["name"]), len(groups[n]), cards(groups[n], show_type)))
    if groups.get(0):
        nav.append(("more", "More"))
        out.append('<section class="lib-group" id="more"><h2>More <span class="lib-count">%d</span></h2>%s</section>' % (len(groups[0]), cards(groups[0], show_type)))
    return nav, "".join(out)


def build_types():
    for key, t in TYPES.items():
        items = [x for x in ENTRIES if x["type"] == key]
        lead = e(t["blurb"]) + " Every entry links to the original."
        intro = ""
        hero_jump = ""
        if key in ("voice", "curriculum"):
            items = sorted(items, key=lambda x: x["title"].lower())
            nav, sections = [], '<section class="lib-group">%s</section>' % cards(items, False, "h2")
        elif key == "learn":
            nav = []
            staff = [x for x in items if x.get("staff")]
            def staff_card(x):
                return ('<article class="lib-card lib-staff"><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3>'
                        '<p class="lib-by">%s</p><p class="lib-start-label">Talk about it afterwards</p><ul>%s</ul>'
                        '<p class="lib-card-foot"><span class="lib-source">Opens at %s</span></p></article>'
                        % (ea(x["url"]), title_html(x["title"]), NEWTAB, " &middot; ".join(e(b) for b in [x["by"]] + shown_meta(x) if b),
                           "".join("<li>%s</li>" % e(q) for q in x["staff"]), e(domain_of(x["url"]))))
            if staff:
                intro = ('<section class="lib-group" id="staff"><h2>Run it as a staff session</h2><p class="lib-group-lead">Recordings that suit a whole-staff meeting, '
                         'each with a couple of prompts to get the conversation going.</p><div class="lib-grid">%s</div>' % "".join(staff_card(x) for x in staff[:3]))
                if len(staff) > 3:
                    intro += ('<details class="lib-expand"><summary>Show all %d staff sessions</summary><div class="lib-grid">%s</div></details>'
                              % (len(staff), "".join(staff_card(x) for x in staff[3:])))
                intro += "</section>"
                nav = [("staff", "Run it as a staff session"), ("all", "All sessions and filters")]
            hero_jump = jump([("all", "Jump to all sessions and filters")])
            sections = ('<section class="lib-group" id="all"><h2>All sessions <span class="lib-count">%d</span></h2><p class="lib-group-lead">Use the categories and filters to find a session '
                        'for the topic you are working on. Sessions marked "Free account needed" open on the host\'s page, where a free sign-in unlocks the recording. '
                        'If a webinar or recorded session has shaped your thinking, <a href="mailto:%s?subject=Learn%%20suggestion">send it my way</a>.</p>%s</section>'
                        % (len(items), EMAIL, filtered_list(items, "learn")))
        elif key in ("watch", "listen"):
            nav = []
            heading = "All videos" if key == "watch" else "Episodes by category"
            glead = ("Looking for something specific? Use the categories and search below to find episodes on the topic you're working on."
                     if key == "listen" else "Use the categories and filters to find footage for a particular professional learning focus.")
            sections = ('<section class="lib-group" id="all"><h2>%s <span class="lib-count">%d</span></h2><p class="lib-group-lead">%s</p>%s</section>'
                        % (heading, len(items), glead, filtered_list(items, key)))
        elif key == "research":
            nav, sections = domain_sections(items)
        else:
            nav, sections = grouped_sections(items)
        if key == "read" and SUBSTACKS:
            def stack_card(x):
                pace = "Posts most weeks" if x["n365"] >= 20 else ("A couple of posts a month" if x["n365"] >= 10 else "Posts now and then")
                return ('<article class="lib-card lib-stack"><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3><p class="lib-by">%s</p>'
                        '<p class="lib-summary">%s</p><p class="lib-card-foot"><span class="lib-tag">%s</span><span class="lib-source">Opens at %s</span></p></article>'
                        % (ea(x["url"]), title_html(x["title"]), NEWTAB, e(x["by"]), e(x["desc"]), pace, e(domain_of(x["url"]))))
            must = [x for name in MUST_SUBSTACKS for x in SUBSTACKS if x["title"] == name]
            intro = ('<section class="lib-group" id="substacks"><h2>Substacks worth following <span class="lib-count">%d</span></h2>'
                     '<p class="lib-group-lead">Some of the best thinking in education now arrives by newsletter. These are free to subscribe to, though some writers keep '
                     'part of their work for paying subscribers. Know one that belongs here? <a href="mailto:%s?subject=Substack%%20suggestion">Send it my way</a>.</p>' % (len(SUBSTACKS), EMAIL))
            if must:
                intro += '<h3 class="lib-subhead">My must-follows</h3><div class="lib-grid">%s</div>' % "".join(stack_card(x) for x in must)
            for region in ["Australia", "United Kingdom and Europe", "United States and Canada"]:
                group = [x for x in SUBSTACKS if x["region"] == region and x not in must]
                if group:
                    intro += '<h3 class="lib-subhead">%s</h3><div class="lib-grid">%s</div>' % (title_html(region), "".join(stack_card(x) for x in group))
            intro += '</section><h2 class="lib-frame" id="articles">Articles and guides by area</h2>'
            nav = [("substacks", "Substacks")] + nav
        if key == "listen" and SHOWS:
            top = [s for name in TOP_SHOWS for s in SHOWS if s["title"] == name]
            rest = [s for s in SHOWS if s not in top]
            def show_card(s):
                # Cover art is loaded from the podcast platform's own image address; nothing is copied to this site.
                if s.get("art"):
                    icon = '<img class="lib-show-art" src="%s" alt="" width="72" height="72" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.style.visibility=\'hidden\'">' % ea(s["art"])
                else:
                    icon = '<span class="lib-show-art lib-show-initial" aria-hidden="true">%s</span>' % e(s["title"][:1])
                listen = []
                host = domain_of(s["url"])
                platform = {"podcasts.apple.com": "Apple Podcasts", "youtube.com": "YouTube", "open.spotify.com": "Spotify"}.get(host)
                if s.get("spotify"):
                    listen.append('<a href="%s" target="_blank" rel="noopener">Listen on Spotify%s</a>' % (ea(s["spotify"]), NEWTAB))
                if s.get("apple") and (s["apple"] != s["url"] or not listen):
                    listen.append('<a href="%s" target="_blank" rel="noopener">Listen on Apple Podcasts%s</a>' % (ea(s["apple"]), NEWTAB))
                # The line under the buttons says where the heading's own link goes. A platform is named as one
                # ("Also on YouTube"), not as the show's website, and is left out when a button already goes there.
                if platform and any("Listen on %s<" % platform in b for b in listen):
                    foot = ""
                elif platform:
                    foot = '<p class="lib-card-foot"><span class="lib-source">Also on %s</span></p>' % platform
                else:
                    foot = '<p class="lib-card-foot"><span class="lib-source">%s %s</span></p>' % (label_html("Show website:") if listen else "Opens at", e(host))
                bits = [s["by"]] + s["meta"] + ([s["note"]] if s.get("note") else [])
                return ('<article class="lib-card lib-show">%s<div><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3><p class="lib-by">%s</p>%s'
                        '%s%s</div></article>'
                        % (icon, ea(s["url"]), title_html(s["title"]), NEWTAB, " &middot; ".join(e(b) for b in bits if b),
                           ('<p class="lib-summary">%s</p>' % e(s["desc"])) if s.get("desc") else "",
                           ('<p class="lib-listen">%s</p>' % "".join(listen)) if listen else "", foot))
            intro = ('<section class="lib-group" id="shows"><h2>Five must-listen podcasts</h2><p class="lib-group-lead">These are currently my favourites, the ones in high rotation. '
                     'I\'m always welcoming new suggestions too, so if you\'ve got a favourite that I\'ve neglected to include, '
                     '<a href="mailto:%s?subject=Podcast%%20suggestion">shoot it my way</a> so I can get listening.</p>'
                     '<div class="lib-grid">%s</div>' % (EMAIL, "".join(show_card(s) for s in top)))
            if rest:
                intro += ('<h3 class="lib-subhead lib-subhead-first" id="more">More great podcasts <span class="lib-count">%d</span></h3>'
                          '<p class="lib-group-lead">Broad, general suggestions. Most of these shows range across many topics.</p><div class="lib-grid">%s</div>'
                          % (len(rest), "".join(show_card(s) for s in sorted(rest, key=lambda s: s["title"].lower()))))
            intro += "</section>"
            nav = [("shows", "Five must-listen podcasts")] + ([("more", "More great podcasts")] if rest else []) + [("all", "Episodes and filters")]
            hero_jump = jump([("all", "Jump to all episodes and filters")])
        toc = ('<nav class="lib-toc" aria-label="On this page">%s%s</nav>' % (label_html("Jump to:"), "".join('<a href="#%s">%s</a>' % (i, e(l)) for i, l in nav))) if nav else ""
        body = hero("Library", t["title"], lead, crumbs=[("Library", "library.html"), (t["title"], None)], extra=hero_jump, art=key)
        body += '<section class="section lib-list"><div class="container">%s%s%s<div class="lib-end">%s</div></div></section>' % (toc, intro, sections, suggest_box())
        write(t["page"], "%s | The Knowledge Nest Library" % t["title"],
              "%d %s in the free Knowledge Nest Library, chosen for teachers and school leaders. Every entry links to the original and names its creator." % (len(items), t["noun"]),
              body, t["title"])


# ---------- area pages ----------
def build_areas():
    grouped = by_area(ENTRIES)
    for a in AREAS:
        items = grouped.get(a["n"], [])
        if not items:
            continue
        present = [k for k in TYPES if any(x["type"] == k for x in items)]
        chips = '<p class="lib-practices">%s%s</p>' % (label_html("Practices in this area:"), "".join("<em>%s</em>" % e(p[0].upper() + p[1:]) for p in a["practices"]))
        body = hero(a["domain"], a["name"], e(a["about"]), crumbs=[("Library", "library.html"), (a["domain"], domain_page(a["domain"], {n: len(v) for n, v in grouped.items()}) if len(domain_areas(a["domain"], {n: len(v) for n, v in grouped.items()})) > 1 else "library.html#areas"), (a["name"], None)],
                    extra=chips + jump([(k, TYPES[k]["label"]) for k in present]))
        sections = ""
        for k in present:
            sub = [x for x in items if x["type"] == k]
            sections += '<section class="lib-group" id="%s"><h2>%s <span class="lib-count">%d</span></h2>%s</section>' % (k, TYPES[k]["label"], len(sub), cards(sub, False))
        related = "".join('<li><a href="%s">%s</a></li>' % (area_page(b), e(b["name"])) for b in AREAS
                          if b["domain"] == a["domain"] and b["n"] != a["n"] and grouped.get(b["n"]))
        side = ""
        if related:
            side += '<div class="lib-side-box"><h2>Related areas</h2><ul>%s</ul></div>' % related
        side += ('<div class="lib-side-box lib-side-navy"><h2>For Victorian schools</h2><p>See podcast episodes matched to the Victorian Teaching and Learning Model 2.0.</p>'
                 '<p><a href="library-vtlm.html">Podcasts by the VTLM 2.0 %s</a></p></div>' % ARROW)
        side += suggest_box()
        body += '<section class="section lib-list"><div class="container lib-two"><div class="lib-main">%s</div><aside class="lib-side" aria-label="Related areas and links">%s</aside></div></section>' % (sections, side)
        write(area_page(a), "%s | The Knowledge Nest Library" % a["name"],
              "%d free videos, podcasts, articles and research on %s, collected for teachers and school leaders." % (len(items), short_area(a["n"])[0].lower() + short_area(a["n"])[1:]),
              body, a["name"])


# ---------- Victorian view ----------
def build_vtlm():
    nav, sections, i = [], "", 0
    labels = {"VTLM 2.0: learning": "Elements of learning", "VTLM 2.0: teaching": "Elements of teaching", "Victorian priority": "Victorian priorities"}
    for frame, groups in VTLM.items():
        sections += '<h2 class="lib-frame">%s</h2>' % title_html(labels.get(frame, frame))
        for element, rows in groups.items():
            i += 1
            nav.append(("v%d" % i, element))
            lis = "".join(
                '<article class="lib-card"><p class="lib-focus">%s</p><h4 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h4>'
                '<p class="lib-by">%s</p><p class="lib-card-foot"><span class="lib-source">Opens at %s</span></p></article>'
                % (e(r["focus"]), ea(r["url"]), title_html(r["title"]), NEWTAB, " &middot; ".join(b for b in [e(r["by"]), ("with " + e(r["guest"])) if r["guest"] else ""] if b), e(domain_of(r["url"])))
                for r in rows)
            sections += '<section class="lib-group" id="v%d"><h3>%s <span class="lib-count">%d</span></h3><div class="lib-grid">%s</div></section>' % (i, title_html(element), len(rows), lis)
    toc = '<nav class="lib-toc" aria-label="On this page">%s%s</nav>' % (label_html("Jump to:"), "".join('<a href="#%s">%s</a>' % (a, e(b)) for a, b in nav))
    lead = ("Podcast episodes matched to the elements of the Victorian Teaching and Learning Model 2.0 and to current Victorian priorities. "
            "The grouping is this library's own and is not endorsed by the Department of Education.")
    body = hero("For Victorian schools", "Podcasts by the VTLM 2.0", lead, crumbs=[("Library", "library.html"), ("Podcasts by the VTLM 2.0", None)])
    body += '<section class="section lib-list"><div class="container">%s%s<div class="lib-end">%s</div></div></section>' % (toc, sections, suggest_box())
    write("library-vtlm.html", "Podcasts by the VTLM 2.0 | The Knowledge Nest Library",
          "Podcast episodes for Victorian teachers and leaders, grouped by the elements of the Victorian Teaching and Learning Model 2.0.", body, "Podcasts by the VTLM 2.0")


def build_404():
    search = ('<form class="lib-search" role="search" action="library" method="get"><label class="sr-only" for="q404">Search the library</label>'
              '<input type="search" id="q404" name="q" placeholder="Search the library" autocomplete="off" maxlength="100">'
              '<button type="submit" class="btn btn-primary">Search</button></form>')
    body = hero("Page not found", "This page has flown the nest",
                "The page you were after has moved or no longer exists. Try a search, or pick a shelf below.", extra=search, art="notfound")
    body += '<section class="section"><div class="container">%s</div></section>' % type_tiles()
    write("404.html", "Page not found | Knowledge Nest", "The page you were looking for could not be found.", body)
    path = os.path.join(ROOT, "404.html")
    html = open(path, encoding="utf8").read().replace("<head>", '<head>\n  <meta name="robots" content="noindex">\n  <base href="/">', 1)
    html = html.replace('<a href="library.html" class="active" aria-current="page">Library</a>', '<a href="library.html">Library</a>', 1)
    open(path, "w", encoding="utf8").write(html)


def build_home_block():
    """Refreshes the library sections on the site's home page, between the LIBRARY markers."""
    path = os.path.join(ROOT, "index.html")
    src = open(path, encoding="utf8").read()
    start, end = "<!-- LIBRARY:START (generated by library/build.py, do not edit by hand) -->", "<!-- LIBRARY:END -->"
    if start not in src or end not in src:
        return
    block = ('<section class="section" id="types"><div class="container"><div class="section-header"><p class="kn-eyebrow">%d resources, free to browse</p><h2>Browse the library</h2>'
             '<p>Pick a shelf to start. Every resource links to its creator\'s original.</p></div>%s</div></section>' % (len(ENTRIES), type_tiles())
             + start_here(3).replace('<section class="section" id="start">', '<section class="section section-tint" id="start">')
             + credit_panels())
    src = src[:src.index(start) + len(start)] + "\n" + block + "\n" + src[src.index(end):]
    open(path, "w", encoding="utf8").write(src)


def build_search_index():
    idx = []
    for x in ENTRIES:
        c = cap_after_colon
        row = {"t": c(x["title"]), "b": c(x["by"]), "u": x["url"], "y": x["type"], "m": [c(m) for m in shown_meta(x)],
               "a": [c(AREA[n]["name"]) for n in x["areas"]], "g": [c(g) for g in shown_tags(x)], "d": domain_of(x["url"])}
        words = " ".join(v for v in [x.get("focus", ""), x.get("summary", "")] if v)   # searched, not shown
        if words:
            row["s"] = c(words)
        idx.append(row)
    json.dump(idx, open(os.path.join(ROOT, "library-search.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))


def build_sitemap():
    static = ["index.html", "library.html", "resources.html", "about.html", "enquiry.html"]
    pages = static + [p for p in BUILT if p != "library.html"]
    today = date.today().isoformat()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml += ["  <url>", "    <loc>%s</loc>" % public(p), "    <lastmod>%s</lastmod>" % today, "  </url>"]
    xml.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(xml) + "\n")


def warnings():
    """Things worth a look before publishing. None of them stops the build."""
    out = []
    # House style: running text has no colon before a list or clause, because the capital the colon rule adds would
    # land in the middle of a sentence. Reword with "covering", "including", "namely" or two sentences.
    prose = [("summary of '%s'" % x["title"], x.get("summary", "")) for x in ENTRIES]
    prose += [("staff prompt of '%s'" % x["title"], q) for x in ENTRIES for q in x.get("staff", [])]
    prose += [("about text of area '%s'" % a["name"], a.get("about", "")) for a in AREAS]
    prose += [("description of show '%s'" % s["title"], s.get("desc", "")) for s in SHOWS]
    prose += [("description of Substack '%s'" % s["title"], s.get("desc", "")) for s in SUBSTACKS]
    prose += [("Start here text '%s'" % t["title"], t["text"]) for t in START_HERE]
    prose += [("domain text '%s'" % d, text) for d, text in DOMAIN_ABOUT.items()]
    for where, text in prose:
        if text and _COLON.sub(_cap, text) != text:
            out.append("colon before a lower-case word in the %s: %s" % (where, text))
    for t in START_HERE:
        for p in t["picks"]:
            if not any(cap_after_colon(x["title"]).startswith(cap_after_colon(p)) for x in ENTRIES):
                out.append("Start here pick '%s' (%s) matches no title, so another entry is shown in its place" % (p, t["title"]))
    for x in ENTRIES:
        if any(str(m).strip().lower() in ("none", "") for m in x["meta"]):
            out.append("empty or 'None' detail left out of the card for '%s': %r" % (x["title"], x["meta"]))
    return out


if __name__ == "__main__":
    build_home()
    build_types()
    build_areas()
    build_domains()
    build_vtlm()
    build_home_block()
    build_search_index()
    build_sitemap()
    build_404()
    print("Built %d library pages from %d entries." % (len(BUILT), len(ENTRIES)))
    print("Colon rule: capital added after a colon in %d texts." % len(CAP_CHANGED))
    for w in warnings():
        print("WARNING: " + w)
