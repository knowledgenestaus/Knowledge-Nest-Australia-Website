#!/usr/bin/env python3
"""Builds the Knowledge Nest Library pages.

Reads library/data/library.json and writes library*.html, library-search.json
and sitemap.xml into the site root. The page header, navigation and footer are
copied from about.html so the library always matches the rest of the site.

Run from the site root:  python3 library/build.py
"""
import html
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

# Broad topics for filtering long lists, built from the focus areas.
TOPICS = OrderedDict([
    ("Literacy and English", [7, 8, 9, 10, 11]),
    ("Maths", [12]),
    ("Classroom teaching", [2, 3, 4, 5, 23, 24]),
    ("How learning works", [1, 15]),
    ("Curriculum", [6]),
    ("Assessment and tiered support", [13, 14]),
    ("Instructional coaching and professional learning", [16]),
    ("Leadership and culture", [19, 20, 21]),
    ("Implementation and change", [17, 22]),
    ("Evidence and debates", [18]),
])

# How the other podcast shows are grouped on the Listen page.
SHOW_GROUPS = OrderedDict([
    ("Teaching and learning", ["General teaching", "How learning works", "Curriculum", "Leadership"]),
    ("Literacy and English", ["Reading and phonics"]),
    ("Maths", ["Maths"]),
    ("Instructional coaching", ["Coaching and PL"]),
    ("Behaviour, inclusion and support", ["Behaviour and culture", "Inclusion and support", "Tiered support"]),
])


def topics_of(x):
    return [t for t, ns in TOPICS.items() if set(ns) & set(x["areas"])]


# Shows featured at the top of the Listen page, in order.
TOP_SHOWS = ["Sold a Story", "Jones & McLean", "Chalk Dust", "Education Research Reading Room", "Mind the Gap: Making Education Work Across the Globe"]

# "Start here" on the library home. Each topic links to its areas and offers up to three picks,
# chosen by matching the start of a title; if a pick is missing, the first entry of that type is used.
START_HERE = [
    dict(title="Change management and implementation", areas=[17, 22],
         text="Whatever you want to improve, the first questions are the same: where to start, which goals to set, and how to lead people through the change.",
         picks=["A School's Guide to Implementation", "097 Implementation", "028 Reducing Change", "Building and operating an effective implementation team"]),
    dict(title="Explicit instruction", areas=[2, 4, 23],
         text="What a well-built lesson looks like, from the first explanation to independent practice, with every student taking part.",
         picks=["Explicit instruction: topic page", "060 Explicit Instruction", "Teach explicitly: Primary and secondary"]),
    dict(title="Structured literacy", areas=[7, 8, 9, 10],
         text="Phonics and fluency, comprehension and vocabulary, spelling and writing, taught systematically from Foundation to Year 6.",
         picks=["How to Teach a Phonics Lesson", "S7 E2 The Top 5 Ways", "029 How to Teach Students to Write"]),
    dict(title="Multi-tiered systems of support and inclusion", areas=[14],
         text="How strong whole-class teaching, early screening and targeted intervention fit together so every student gets the right support.",
         picks=["Leading MTSS", "S04E10", "S5 E17 MTSS for Reading"]),
    dict(title="Assessment and reporting", areas=[13, 4],
         text="Which assessments answer which questions, and how to use what they tell you without drowning in data.",
         picks=["027 Assessment", "S03E04", "Using data in MTSS: screening"]),
]

AREAS = sorted(DATA["areas"], key=lambda a: a["n"])
AREA = {a["n"]: a for a in AREAS}
ENTRIES = DATA["entries"]
SHOWS = DATA["shows"]
VTLM = DATA["vtlm"]

TYPES = OrderedDict([
    ("watch", dict(label="Watch", page="library-watch.html", title="Classroom videos", noun="videos", colour="navy",
                   blurb="Real classroom footage and webinars showing practice in action.",
                   icon='<rect x="4" y="7" width="22" height="16" rx="2"/><path d="M13 11l6 4-6 4z"/>')),
    ("listen", dict(label="Listen", page="library-listen.html", title="Podcasts", noun="podcast episodes", colour="terracotta",
                    blurb="Podcast episodes sorted by subject and by practice.",
                    icon='<path d="M6 17v-2a9 9 0 0118 0v2"/><rect x="4" y="17" width="5" height="8" rx="1.500"/><rect x="21" y="17" width="5" height="8" rx="1.500"/>')),
    ("read", dict(label="Read", page="library-read.html", title="Articles and blogs", noun="articles and guides", colour="eucalyptus",
                  blurb="Short reads, blogs, explainers and practice guides.",
                  icon='<path d="M15 7C13 5 10 4 6 4v18c4 0 7 1 9 3 2-2 5-3 9-3V4c-4 0-7 1-9 3z"/><path d="M15 7v18"/>')),
    ("research", dict(label="Research", page="library-research.html", title="Research", noun="papers and reviews", colour="gold",
                      blurb="Foundational papers, reviews and meta-analyses.",
                      icon='<circle cx="13" cy="13" r="8"/><path d="M19 19l7 7"/>')),
    ("voice", dict(label="Voices", page="library-voices.html", title="Voices to follow", noun="people to follow", colour="navy",
                   blurb="The researchers, teachers and writers worth your time.",
                   icon='<circle cx="11" cy="10" r="4.500"/><path d="M3 25c.6-4.500 3.800-7 8-7s7.400 2.500 8 7"/><circle cx="22" cy="11" r="3"/><path d="M22 17c3 .2 4.800 2 5.200 5"/>')),
    ("curriculum", dict(label="Curriculum", page="library-curriculum.html", title="Free curriculum", noun="curriculum collections", colour="terracotta",
                        blurb="Openly available lesson materials, scope and sequences.",
                        icon='<rect x="5" y="3" width="20" height="24" rx="2"/><path d="M10 10h10M10 15h10M10 20h6"/>')),
])

DOMAIN_ORDER = []
for a in AREAS:
    if a["domain"] not in DOMAIN_ORDER:
        DOMAIN_ORDER.append(a["domain"])
# keep the order used on the Framework tab: A to H
DOMAIN_ORDER = ["How learning works", "Teaching practice", "Curriculum and subject teaching", "Assessment and support",
                "Coaching and professional learning", "Leadership and culture", "Implementation and change", "Evidence literacy"]

e = html.escape
NEWTAB = '<span class="sr-only"> (opens in a new tab)</span>'
ARROW = '<span aria-hidden="true">&rarr;</span>'


def area_page(a):
    return "library-%s.html" % a["slug"]


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


def card(x, show_type=True, level="h3", filterable=False):
    t = TYPES[x["type"]]
    bits = [e(m) for m in x["meta"]]
    by = e(x["by"]) if x["by"] else ""
    line = " &middot; ".join([b for b in [by] + bits if b])
    tags = "".join('<span class="lib-tag%s">%s</span>' % (" lib-tag-free" if tg.lower().startswith("free") else "", e(tg)) for tg in x["tags"])
    badge = '<span class="lib-type lib-type-%s">%s</span>' % (x["type"], t["label"]) if show_type else ""
    focus = '<p class="lib-focus">%s</p>' % e(x["focus"]) if x.get("focus") else ""
    summary = '<p class="lib-summary">%s</p>' % e(x["summary"]) if x.get("summary") else ""
    topics = ""
    data = ""
    if filterable:
        topics = '<p class="lib-topics">%s</p>' % "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(short_area(n))) for n in x["areas"]) if x["areas"] else ""
        text = " ".join([x["title"], x["by"], x.get("summary", ""), x.get("focus", ""), " ".join(x["meta"])] + [AREA[n]["name"] for n in x["areas"]]).lower()
        data = ' data-topics="%s" data-areas="%s" data-bands="%s" data-subject="%s" data-region="%s" data-by="%s" data-text="%s"' % (
            e("|".join(topics_of(x))), ",".join(str(n) for n in x["areas"]), ",".join(x.get("bands", [])), e(x.get("subject", "")), e(x.get("region", "")), e(x["by"]), e(text))
    return (
        '<article class="lib-card" data-type="%s"%s>%s%s<%s class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></%s>'
        '%s%s%s<p class="lib-card-foot">%s<span class="lib-source">Opens at %s</span></p></article>'
        % (x["type"], data, badge, focus, level, e(x["url"]), e(x["title"]), NEWTAB, level,
           ('<p class="lib-by">%s</p>' % line) if line else "", summary, topics, tags, e(domain_of(x["url"])))
    )


def cards(entries, show_type=True, level="h3", filterable=False):
    return '<div class="lib-grid">%s</div>' % "".join(card(x, show_type, level, filterable) for x in entries)


def options(values, all_label):
    return '<option value="">%s</option>%s' % (e(all_label), "".join('<option value="%s">%s</option>' % (e(v), e(l)) for v, l in values))


def filter_bar(items, kind):
    """Filter controls for a long list. Works without JavaScript as a plain list."""
    area_ns = [a["n"] for d in DOMAIN_ORDER for a in AREAS if a["domain"] == d and any(a["n"] in x["areas"] for x in items)]
    topic_names = [t for t in TOPICS if any(t in topics_of(x) for x in items)]
    fields = ['<div class="lib-field"><label for="fTopic">Topic</label><select id="fTopic" data-filter="topics">%s</select></div>'
              % options([(t, t) for t in topic_names], "All topics")]
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
    by_label = "Source" if kind == "watch" else "Show"
    sources = sorted(set(x["by"] for x in items if x["by"]), key=str.lower)
    fields.append('<div class="lib-field"><label for="fBy">%s</label><select id="fBy" data-filter="by">%s</select></div>'
                  % (by_label, options([(v, v) for v in sources], "All %ss" % by_label.lower())))
    fields.append('<div class="lib-field lib-field-wide"><label for="fText">Search within this page</label>'
                  '<input type="search" id="fText" placeholder="e.g. worked examples" autocomplete="off"></div>')
    chips = "".join('<button type="button" class="lib-chip" data-topic="%s">%s <span>%d</span></button>'
                    % (e(t), e(t), sum(1 for x in items if t in topics_of(x))) for t in topic_names)
    return ('<div class="lib-chips" id="libChips" hidden><p>Browse by topic</p><div>%s</div></div>' % chips +
            '<form class="lib-filters" id="libFilters" hidden><div class="lib-filter-row">%s</div>'
            '<p class="lib-filter-status"><span id="fCount" role="status" aria-live="polite"></span> '
            '<button type="reset" class="lib-reset">Clear filters</button></p></form>' % "".join(fields))


def filtered_list(items, kind):
    order = {a["n"]: i for i, a in enumerate(sorted(AREAS, key=lambda a: (DOMAIN_ORDER.index(a["domain"]), a["n"])))}
    items = sorted(items, key=lambda x: (order.get(x["areas"][0], 99) if x["areas"] else 99))
    return (filter_bar(items, kind) + '<div id="libList">%s</div>' % cards(items, False, "h3", True)
            + '<p class="lib-more" hidden><button type="button" class="btn btn-primary" id="libMore">Show more</button></p>'
            + '<p class="lib-empty" id="libEmpty" hidden>Nothing matches those filters yet. Try clearing one, or <a href="%s">email a suggestion</a>.</p>' % SUGGEST
            + '<script src="library/filter.js?v=2" defer></script>')


WAVE = ('<div class="wave-bottom"><svg aria-hidden="true" focusable="false" viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M0,25 C240,55 480,5 720,30 C960,55 1200,8 1440,28 L1440,60 L0,60 Z" fill="#ffffff"/>'
        '<path d="M0,25 C240,55 480,5 720,30 C960,55 1200,8 1440,28" fill="none" stroke="rgba(232,213,183,0.3)" stroke-width="2" stroke-dasharray="8,10" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg></div>')


def hero(tagline, h1, lead, crumbs=None, extra=""):
    crumb = ""
    if crumbs:
        parts = ['<a href="%s">%s</a>' % (h, e(l)) if h else e(l) for l, h in crumbs]
        crumb = '<p class="lib-crumbs">%s</p>' % " <span aria-hidden=\"true\">/</span> ".join(parts)
    return ('<section class="page-hero lib-hero"><div class="container"><div class="page-hero-text lib-hero-text">%s'
            '<p class="hero-tagline">%s</p><h1>%s</h1><p>%s</p>%s</div></div>%s</section>'
            % (crumb, e(tagline), e(h1), lead, extra, WAVE))


def start_here():
    cards_html = []
    for t in START_HERE:
        pool = [x for x in ENTRIES if set(x["areas"]) & set(t["areas"])]
        picks = []
        for p in t["picks"]:
            hit = next((x for x in ENTRIES if x["title"].startswith(p)), None)
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
                      % (x["type"], TYPES[x["type"]]["label"], e(x["url"]), e(x["title"]), NEWTAB) for x in picks[:3])
        links = "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(short_area(n))) for n in t["areas"])
        cards_html.append('<article class="lib-start"><h3>%s</h3><p>%s</p><p class="lib-start-label">Three to begin with</p><ul>%s</ul>'
                          '<p class="lib-start-label">See everything on</p><p class="lib-topics">%s</p></article>' % (e(t["title"]), e(t["text"]), lis, links))
    return ('<section class="section" id="start"><div class="container"><div class="section-header"><h2>Start here</h2>'
            '<p>Five starting points for a school\'s professional learning journey.</p><div class="section-rule"></div></div>'
            '<div class="lib-starts">%s</div></div></section>' % "".join(cards_html))


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
            '<div class="lib-panel lib-panel-navy"><p class="lib-eyebrow">Help it grow</p><h2>Know something that belongs here?</h2>'
            "<p>This library is built by sharing. If there is a video, podcast, article or piece of research that has helped you or your team, "
            "send a quick email with the link and it can be added for everyone.</p>"
            '<p><a href="%s" class="btn btn-sandstone">Email a suggestion</a></p></div></div></div></section>' % (EMAIL, SUGGEST))


def suggest_box():
    return ('<div class="lib-side-box"><h2>Something missing?</h2><p>This library is built by sharing. Send a quick email with a link and it can be added for everyone.</p>'
            '<p><a href="%s" class="btn btn-primary btn-sm">Email a suggestion</a></p></div>' % SUGGEST)


# ---------- page shell, copied from about.html ----------
def shell():
    src = open(os.path.join(ROOT, "about.html"), encoding="utf8").read()
    head = src[:src.index("<main")]
    tail = src[src.index("</main>"):]
    head = head.replace(' class="active" aria-current="page"', "")
    head = head.replace('<a href="library.html">Library</a>', '<a href="library.html" class="active" aria-current="page">Library</a>', 1)
    head = re.sub(r'<script type="application/ld\+json">.*?</script>', "@@LD@@", head, flags=re.S)
    tail = tail.replace('<div class="footer-bottom">',
                        '<p class="footer-credit">The Library is a curated collection of other people\'s work. Every entry credits its creator and links to the original source.</p>\n    <div class="footer-bottom">', 1)
    return head, tail


HEAD, TAIL = shell()
BUILT = []


def write(name, title, desc, body, crumb_name=None):
    head = HEAD
    head = re.sub(r"<title>.*?</title>", "<title>%s</title>" % e(title), head, flags=re.S)
    head = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + e(desc), head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + e(desc), head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + e(title), head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*', lambda m: m.group(1) + SITE + name, head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + SITE + name, head)
    items = [("Home", SITE), ("Library", SITE + "library.html")]
    if crumb_name:
        items.append((crumb_name, SITE + name))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}
    head = head.replace("@@LD@@", '<script type="application/ld+json">\n%s\n  </script>' % json.dumps(ld, indent=2))
    page = head + '<main id="main-content" tabindex="-1">\n' + body + "\n" + TAIL
    open(os.path.join(ROOT, name), "w", encoding="utf8").write(page)
    BUILT.append(name)


def count(t):
    return sum(1 for x in ENTRIES if x["type"] == t)


def type_tiles():
    out = []
    for key, t in TYPES.items():
        out.append(
            '<a href="%s" class="explore-tile"><span class="card-icon %s"><svg aria-hidden="true" focusable="false" viewBox="0 0 30 30" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg></span>'
            '<span class="explore-tile-body"><span class="explore-tile-title">%s</span><span class="explore-tile-text">%s</span>'
            '<span class="explore-tile-cta">%d %s %s</span></span></a>'
            % (t["page"], t["colour"], t["icon"], e(t["label"] if key != "voice" else "Voices to follow") if key != "curriculum" else "Free curriculum",
               e(t["blurb"]), count(key), e(t["noun"]), ARROW))
    return '<div class="explore-grid">%s</div>' % "".join(out)


def area_index(counts):
    cols = []
    for d in DOMAIN_ORDER:
        links = "".join('<li><a href="%s">%s</a> <span class="lib-count">%d</span></li>' % (area_page(a), e(a["name"]), counts.get(a["n"], 0))
                        for a in AREAS if a["domain"] == d and counts.get(a["n"], 0))
        if links:
            cols.append('<div class="lib-domain"><h3>%s</h3><ul>%s</ul></div>' % (e(d), links))
    return '<div class="lib-domains">%s</div>' % "".join(cols)


def jump(pairs):
    return '<p class="page-hero-jump">%s</p>' % "".join('<a href="#%s">%s</a>' % (i, e(l)) for i, l in pairs)


# ---------- library home ----------
def build_home():
    counts = {n: len(v) for n, v in by_area(ENTRIES).items()}
    popular = [2, 7, 10, 16, 17, 4]
    chips = "".join('<a href="%s">%s</a>' % (area_page(AREA[n]), e(AREA[n]["name"].split(":")[0].split(",")[0])) for n in popular)
    search = ('<form class="lib-search" role="search" id="libSearch" action="library.html" method="get">'
              '<label for="q" class="sr-only">Search the library</label>'
              '<input type="search" id="q" name="q" placeholder="Search by topic, practice or person, e.g. hinge questions" autocomplete="off">'
              '<button type="submit" class="btn btn-sandstone">Search</button></form>'
              '<p class="page-hero-jump lib-popular"><span>Popular:</span>%s</p>' % chips)
    lead = ("Great professional learning resources are scattered all over the internet. This library gathers the best of other people's work "
            "in one place, sorted by topic, so you can spend your time learning instead of searching.")
    body = hero("A curated collection, free for teachers and leaders", "The Knowledge Nest Library", lead, extra=search)
    body += ('<section class="section lib-results-section" id="results" hidden><div class="container">'
             '<h2 id="resultsHeading" tabindex="-1">Search results</h2><p class="lib-results-note" id="resultsNote"></p>'
             '<div id="resultsList"></div><p><button type="button" class="btn btn-primary btn-sm" id="clearSearch">Clear search</button></p></div></section>')
    body += start_here()
    body += ('<section class="section section-sandstone-pale" id="types"><div class="container"><div class="section-header"><h2>Browse by type</h2>'
             '<p>Know how you want to learn today? Start here.</p><div class="section-rule"></div></div>%s</div></section>' % type_tiles())
    body += ('<section class="section" id="areas"><div class="container"><div class="section-header"><h2>Browse by area</h2>'
             '<p>Every area gathers videos, podcasts, reading and research in one place.</p><div class="section-rule"></div></div>%s</div></section>'
             % area_index(counts))
    elements = "".join('<span>%s</span>' % e(k) for frame in VTLM for k in VTLM[frame] if frame.startswith("VTLM"))
    body += ('<section class="section section-sandstone-pale"><div class="container"><div class="lib-band"><div class="lib-band-text"><p class="lib-eyebrow">For Victorian schools</p>'
             '<h2>Browse by the Victorian Teaching and Learning Model 2.0</h2>'
             '<p>Podcast episodes matched to each element of learning and teaching, and to current Victorian priorities.</p>'
             '<p><a href="library-vtlm.html" class="btn btn-sandstone">Open the VTLM 2.0 view</a></p></div>'
             '<div class="lib-band-chips">%s</div></div>'
             '<p class="lib-own">Looking for Jo\'s own articles and downloadable guides? <a href="resources.html">Find them here</a>.</p>'
             '</div></section>' % elements)
    body += credit_panels()
    body += '<script src="library/search.js?v=1" defer></script>'
    write("library.html", "The Knowledge Nest Library | Free Professional Learning Resources",
          "A free, curated library of videos, podcasts, blogs, research and curriculum materials to support your school's professional learning journey.",
          body)


# ---------- type pages ----------
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
                   % (n, area_page(AREA[n]), e(AREA[n]["name"]), len(groups[n]), cards(groups[n], show_type)))
    if groups.get(0):
        nav.append(("more", "More"))
        out.append('<section class="lib-group" id="more"><h2>More <span class="lib-count">%d</span></h2>%s</section>' % (len(groups[0]), cards(groups[0], show_type)))
    return nav, "".join(out)


def build_types():
    for key, t in TYPES.items():
        items = [x for x in ENTRIES if x["type"] == key]
        lead = e(t["blurb"]) + " Every entry links to the original."
        intro = ""
        if key in ("voice", "curriculum"):
            items = sorted(items, key=lambda x: x["title"].lower())
            nav, sections = [], '<section class="lib-group">%s</section>' % cards(items, False, "h2")
        elif key in ("watch", "listen"):
            nav = []
            heading = "All videos" if key == "watch" else "Episodes by topic"
            sections = '<section class="lib-group" id="all"><h2>%s <span class="lib-count">%d</span></h2>%s</section>' % (heading, len(items), filtered_list(items, key))
        else:
            nav, sections = grouped_sections(items)
        if key == "listen" and SHOWS:
            top = [s for name in TOP_SHOWS for s in SHOWS if s["title"] == name]
            rest = [s for s in SHOWS if s not in top]
            def show_card(s):
                # Cover art is loaded from the podcast platform's own image address; nothing is copied to this site.
                if s.get("art"):
                    icon = '<img class="lib-show-art" src="%s" alt="" width="72" height="72" loading="lazy" decoding="async" referrerpolicy="no-referrer">' % e(s["art"])
                else:
                    icon = ('<span class="lib-show-icon" aria-hidden="true"><svg viewBox="0 0 30 30" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg></span>'
                            % TYPES["listen"]["icon"])
                listen = []
                if s.get("spotify"):
                    listen.append('<a href="%s" target="_blank" rel="noopener">Listen on Spotify%s</a>' % (e(s["spotify"]), NEWTAB))
                if s.get("apple") and s["apple"] != s["url"]:
                    listen.append('<a href="%s" target="_blank" rel="noopener">Listen on Apple Podcasts%s</a>' % (e(s["apple"]), NEWTAB))
                bits = [s["by"]] + s["meta"] + ([s["note"]] if s.get("note") else [])
                return ('<article class="lib-card lib-show">%s<div><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3><p class="lib-by">%s</p>%s'
                        '%s<p class="lib-card-foot"><span class="lib-source">Opens at %s</span></p></div></article>'
                        % (icon, e(s["url"]), e(s["title"]), NEWTAB, " &middot; ".join(e(b) for b in bits if b),
                           ('<p class="lib-summary">%s</p>' % e(s["desc"])) if s.get("desc") else "",
                           ('<p class="lib-listen">%s</p>' % "".join(listen)) if listen else "", e(domain_of(s["url"]))))
            intro = ('<section class="lib-group" id="shows"><h2>Five must-listen podcasts</h2><p class="lib-group-lead">These are currently my favourites, the ones in high rotation. '
                     'I\'m always welcoming new suggestions too, so if you\'ve got a favourite that I\'ve neglected to include, '
                     '<a href="mailto:%s?subject=Podcast%%20suggestion">shoot it my way</a> so I can get listening.</p>'
                     '<div class="lib-grid">%s</div>' % (EMAIL, "".join(show_card(s) for s in top)))
            intro += '<h3 class="lib-subhead lib-subhead-first">More shows, by category</h3><p class="lib-group-lead">Cover art belongs to each show.</p>'
            for label, subjects in SHOW_GROUPS.items():
                group = sorted([s for s in rest if (s["meta"][0] if s["meta"] else "") in subjects], key=lambda s: s["title"].lower())
                if group:
                    intro += ('<h3 class="lib-subhead">%s <span class="lib-count">%d</span></h3><div class="lib-grid">%s</div>'
                              % (e(label), len(group), "".join(show_card(s) for s in group)))
            other = [s for s in rest if not any((s["meta"][0] if s["meta"] else "") in v for v in SHOW_GROUPS.values())]
            if other:
                intro += '<h3 class="lib-subhead">More</h3><div class="lib-grid">%s</div>' % "".join(show_card(s) for s in other)
            intro += "</section>"
        toc = ('<nav class="lib-toc" aria-label="On this page"><span>Jump to:</span>%s</nav>' % "".join('<a href="#%s">%s</a>' % (i, e(l)) for i, l in nav)) if nav else ""
        body = hero("Library", t["title"], lead, crumbs=[("Library", "library.html"), (t["title"], None)])
        body += '<section class="section lib-list"><div class="container">%s%s%s<div class="lib-end">%s</div></div></section>' % (toc, intro, sections, suggest_box())
        write(t["page"], "%s | The Knowledge Nest Library" % t["title"],
              "%d %s for teachers and school leaders, collected in the Knowledge Nest Library. Every entry links to the original source." % (len(items), t["noun"]),
              body, t["title"])


# ---------- area pages ----------
def build_areas():
    grouped = by_area(ENTRIES)
    for a in AREAS:
        items = grouped.get(a["n"], [])
        if not items:
            continue
        present = [k for k in TYPES if any(x["type"] == k for x in items)]
        chips = '<p class="lib-practices"><span>Practices in this area:</span>%s</p>' % "".join("<em>%s</em>" % e(p[0].upper() + p[1:]) for p in a["practices"])
        body = hero(a["domain"], a["name"], e(a["about"]), crumbs=[("Library", "library.html"), (a["domain"], "library.html#areas"), (a["name"], None)],
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
                 '<p><a href="library-vtlm.html">Open the VTLM 2.0 view %s</a></p></div>' % ARROW)
        side += suggest_box()
        body += '<section class="section lib-list"><div class="container lib-two"><div class="lib-main">%s</div><aside class="lib-side">%s</aside></div></section>' % (sections, side)
        write(area_page(a), "%s | The Knowledge Nest Library" % a["name"],
              "%d free videos, podcasts, articles and research on %s, collected for teachers and school leaders." % (len(items), a["name"][0].lower() + a["name"][1:]),
              body, a["name"])


# ---------- Victorian view ----------
def build_vtlm():
    nav, sections, i = [], "", 0
    labels = {"VTLM 2.0: learning": "Elements of learning", "VTLM 2.0: teaching": "Elements of teaching", "Victorian priority": "Victorian priorities"}
    for frame, groups in VTLM.items():
        sections += '<h2 class="lib-frame">%s</h2>' % e(labels.get(frame, frame))
        for element, rows in groups.items():
            i += 1
            nav.append(("v%d" % i, element.replace("Explicit teaching: ", "")))
            lis = "".join(
                '<article class="lib-card"><p class="lib-focus">%s</p><h4 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h4>'
                '<p class="lib-by">%s</p><p class="lib-card-foot"><span class="lib-source">Opens at %s</span></p></article>'
                % (e(r["focus"]), e(r["url"]), e(r["title"]), NEWTAB, " &middot; ".join(b for b in [e(r["by"]), ("with " + e(r["guest"])) if r["guest"] else ""] if b), e(domain_of(r["url"])))
                for r in rows)
            sections += '<section class="lib-group" id="v%d"><h3>%s <span class="lib-count">%d</span></h3><div class="lib-grid">%s</div></section>' % (i, e(element), len(rows), lis)
    toc = '<nav class="lib-toc" aria-label="On this page"><span>Jump to:</span>%s</nav>' % "".join('<a href="#%s">%s</a>' % (a, e(b)) for a, b in nav)
    lead = ("Podcast episodes matched to the elements of the Victorian Teaching and Learning Model 2.0 and to current Victorian priorities. "
            "The grouping is this library's own and is not endorsed by the Department of Education.")
    body = hero("For Victorian schools", "Listening by the VTLM 2.0", lead, crumbs=[("Library", "library.html"), ("VTLM 2.0 view", None)])
    body += '<section class="section lib-list"><div class="container">%s%s<div class="lib-end">%s</div></div></section>' % (toc, sections, suggest_box())
    write("library-vtlm.html", "Podcasts by the VTLM 2.0 | The Knowledge Nest Library",
          "Podcast episodes for Victorian teachers and leaders, grouped by the elements of the Victorian Teaching and Learning Model 2.0.", body, "VTLM 2.0 view")


def build_search_index():
    idx = []
    for x in ENTRIES:
        idx.append({"t": x["title"], "b": x["by"], "u": x["url"], "y": x["type"], "m": x["meta"],
                    "a": [AREA[n]["name"] for n in x["areas"]], "g": x["tags"], "d": domain_of(x["url"])})
    json.dump(idx, open(os.path.join(ROOT, "library-search.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))


def build_sitemap():
    static = ["", "library.html", "resources.html", "secrets-of-how-we-learn.html", "about.html", "services.html", "enquiry.html"]
    pages = static + [p for p in BUILT if p != "library.html"]
    today = date.today().isoformat()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml += ["  <url>", "    <loc>%s%s</loc>" % (SITE, p), "    <lastmod>%s</lastmod>" % today, "  </url>"]
    xml.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(xml) + "\n")


if __name__ == "__main__":
    build_home()
    build_types()
    build_areas()
    build_vtlm()
    build_search_index()
    build_sitemap()
    print("Built %d library pages from %d entries." % (len(BUILT), len(ENTRIES)))
