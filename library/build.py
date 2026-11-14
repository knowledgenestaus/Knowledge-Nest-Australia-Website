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
from urllib.parse import quote_plus, unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, "library", "data", "library.json"), encoding="utf8"))
SITE = "https://knowledgenest.com.au/"
EMAIL = "jo@knowledgenest.com.au"
SUGGEST = "mailto:%s?subject=Library%%20suggestion" % EMAIL

# Categories for the Listen filters, built from the focus areas. (Watch and Learn use the library's own
# topics and areas of practice instead: see filter_bar.)
TOPICS = OrderedDict([
    ("Explicit instruction", [2, 3, 4, 23, 24]),
    ("Cognitive science", [1, 3, 15]),
    ("English", [11, 26, 27, 28, 29, 30, 31, 32, 10, 33]),
    ("Maths", [34, 35, 36, 37, 38, 39]),
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
INCLUSION_WORDS = re.compile(r"adhd|autis|dyslexi|inclusi|special educational|\bsend\b|adaptive|diverse|twice|exceptional|teaching assistant|learning difficult|neurodiv|disabilit", re.I)


def topics_of(x):
    out = [t for t, ns in TOPICS.items() if set(ns) & set(x["areas"])]
    text = " ".join([x["title"], x.get("focus", ""), x.get("summary", "")])
    mtss = bool(MTSS_WORDS.search(text))
    incl = bool(INCLUSION_WORDS.search(text))
    support = bool({14, 25} & set(x["areas"]))   # tiered support and inclusion; learning difficulties, disorders and additional needs
    if support and not (mtss or incl):
        incl = True
    if mtss and (support or 13 in x["areas"] or re.search(r"mtss|multi-tiered", text, re.I)):
        out.append("Multi-tiered systems of support")
    if incl and (support or INCLUSION_WORDS.search(x["title"])):
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
    dict(title="Structured literacy", areas=[27, 28, 29, 30, 31, 10],
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

# Every video carries a "kind", and the kind decides its shelf. Watch is only video of teachers teaching (the first
# three kinds); everything else you sit down with is Learn. The label is the wording shown on the card.
# Videos live in library.json (type "watch") and learn.json; whichever file an entry is typed into, its kind shelves it.
KIND_LABEL = OrderedDict([
    ("classroom footage", "Lesson footage"),
    ("classroom footage with commentary", "Lesson with commentary"),
    ("demonstration", "Demonstration"),
    ("webinar", "Webinar"),
    ("talk", "Talk"),
    ("explainer", "Explainer"),
    ("school story", "School story"),
    ("interview", "Interview"),
    ("series", "Series"),
])
WATCH_KINDS = ("classroom footage", "classroom footage with commentary", "demonstration")
LEARN = _load("learn.json", {"entries": []})
for x in LEARN["entries"]:
    ENTRIES.append(dict(x, type="learn"))
for x in ENTRIES:
    if x["type"] in ("watch", "learn"):
        if x.get("kind") not in KIND_LABEL:
            raise SystemExit("STOPPED: '%s' has no valid kind (%r), so it cannot be put on a shelf. Use one of: %s."
                             % (x["title"], x.get("kind"), "; ".join(KIND_LABEL)))
        x["type"] = "watch" if x["kind"] in WATCH_KINDS else "learn"
LENGTHS = ["Under 10 minutes", "10 to 30 minutes", "30 to 60 minutes", "Over 60 minutes", "Series"]
NO_LENGTH = "Length not stated"   # the Length menu's option for a Learn entry with no running time recorded
SUBSTACKS = _load("substacks.json", [])
# Weekly featured reading ("This week's reading" on the home page and the Read shelf). See tools/feature_week.py.
# KN_FEATURED_FILE points the build at another copy of the file, for testing.
def _load_featured():
    path = os.environ.get("KN_FEATURED_FILE") or os.path.join(ROOT, "library", "data", "featured.json")
    try:
        data = json.load(open(path, encoding="utf8"))
    except (OSError, ValueError):   # missing, empty or broken: no panel
        return {}
    return data if isinstance(data, dict) else {}
FEATURED = _load_featured()
FEATURED_DAYS = 21   # after this many days from its week_of the panel is left out (and hidden in the browser), so a missed week never shows stale picks
THUMBS = _load("thumbs.json", {})  # video url -> preview image url (linked, never copied); see tools/thumbs.py
# Jo's must-follow Substacks, by title, shown first on the Read page. Leave empty until chosen.
MUST_SUBSTACKS = []
# The order of "Substacks worth following" on Read, by title (Jo, November 2026): Haili Hughes first, then the other
# Australian voices, then the rest. Greg Ashman's two publications sit in the lower half, apart from each other.
# A Substack in substacks.json that is not named here is added at the end, so a new one never disappears.
SUBSTACK_ORDER = [
    "Dr Haili Hughes",
    "Knowledge for Teachers", "Chalk Dust", "Dr Nathaniel Swain", "On Education", "The Disruptive Educator", "Bill Hansberry",
    "VIC Maths Notes", "Shaun Brien", "Kylie Hoey", "Publican Policy", "The Digital Delusion",
    "The Learning Dispatch", "The Learning Spy", "Tips for Teachers", "No More Marking", "Cognitive Coaching", "Tom Sherrington",
    "Dylan Wiliam", "Carousel: Teaching, Learning, Leading", "Andrew Old's Education Battleground", "Powerful Knowledge",
    "100% Assessment", "Filling the Pail", "Christopher Such", "Paul Kirschner", "Curriculum 101", "Jen's Substack",
    "WAGOLL Teaching", "Minding the Gap", "The Bell Ringer", "Doug Lemov's Field Notes", "When Will They Learn?",
    "The Next 30 Years", "Science of Reading Classroom", "SoL in the Wild", "The Science of Learning", "Teach Like a Champion",
    "Making Words Make Sense", "The Curriculum Insight Project", "Mark R Shinn's Peculiar Observations About MTSS Implementation",
    "Daniel Willingham",
]
REGION_SHORT = {"Australia": "Australia", "United Kingdom and Europe": "UK and Europe", "United States and Canada": "US and Canada"}
# Writers who should not open a section of the Read shelf (Jo, November 2026). Their pieces still appear, just not first.
NOT_FIRST_ON_READ = ("Greg Ashman",)
# Read cards show the article's own lead image full width at the top, like Watch and Learn ("top"), or a small square
# beside the heading ("side"). Without an image a "top" card shows the publication's name on pale blue instead.
READ_PICTURE = "top"
# The publication's icon beside the byline on Substack article cards.
BYLINE_ICON = True
SHOWS = DATA["shows"]
SHOW_ART = {s["title"]: s["art"] for s in SHOWS if s.get("art")}  # cover art by show, for episode cards
# Preview images that are video stills (shown edge to edge); anything else is shown whole, like a logo.
STILL_HOSTS = ("ytimg.com", "edresearch.edu.au", "vimeocdn.com", "boltdns.net")
VTLM = DATA["vtlm"]

TYPES = OrderedDict([
    ("watch", dict(label="Watch", page="library-watch.html", title="Watch: Teachers teaching", tile="Watch", noun="classroom videos", short="videos",
                   blurb="Real lessons and short clips of teachers teaching.",
                   promise="Here you'll find real lessons and short clips from real classrooms, often with the teacher or a coach explaining what they did and why.",
                   cross=("Looking for webinars, talks and short explainers?", "They are on the Learn shelf", "library-learn.html"))),
    ("learn", dict(label="Learn", page="library-learn.html", title="Learn: Webinars, talks and explainers", tile="Learn", noun="sessions and explainers", short="sessions",
                   blurb="Webinars, talks, school stories and short explainers to sit down with.",
                   promise="Here I have gathered professional learning to sit down with. There are webinars, talks, school stories and short explainers, for you or for a whole staff.",
                   cross=("Want to see a lesson being taught?", "Classroom footage is on the Watch shelf", "library-watch.html"))),
    ("listen", dict(label="Listen", page="library-listen.html", title="Listen: podcasts", tile="Listen", noun="episodes",
                    blurb="Must-listen shows, and episodes sorted by category.")),
    ("read", dict(label="Read", page="library-read.html", title="Read: articles, blogs and Substacks", tile="Read", noun="articles and guides", short="articles",
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
# The order of the numbers is the order the areas are shown in (Literacy runs as a teacher meets it across the school).
DOMAIN_OF = {
    "Literacy": [11, 26, 27, 28, 29, 30, 31, 32, 10, 33],
    "Maths": [34, 35, 36, 37, 38, 39],
    "Knowledge-rich curriculum": [6],
    "MTSS and assessment": [13, 14, 25],
    "Research and evidence": [18],
}
for a in AREAS:
    for name, ns in DOMAIN_OF.items():
        if a["n"] in ns:
            a["domain"] = name
DOMAIN_ORDER = ["How learning works", "Teaching practice", "Literacy", "Maths", "Knowledge-rich curriculum", "MTSS and assessment",
                "Coaching and professional learning", "Leadership and culture", "Implementation and change", "Research and evidence"]
assert all(a["domain"] in DOMAIN_ORDER for a in AREAS)
# From here on AREAS is in display order: topic by topic, and inside a topic in the order given in DOMAIN_OF (otherwise by number).
AREAS.sort(key=lambda a: (DOMAIN_ORDER.index(a["domain"]),
                          DOMAIN_OF[a["domain"]].index(a["n"]) if a["n"] in DOMAIN_OF.get(a["domain"], []) else a["n"]))
for x in ENTRIES:
    for n in x["areas"]:
        if n not in AREA:
            raise SystemExit("STOPPED: '%s' is tagged to area %r, which does not exist (retired areas are 7, 8, 9 and 12)." % (x["title"], n))

# Area pages that were retired in the November 2026 reorganisation: old file name -> the page that replaces it.
# build_stubs() leaves a small "this page has moved" page at each old address. Nothing links to them.
RETIRED_PAGES = {
    "library-early-reading.html": ("library-phonics.html", "Phonics"),
    "library-comprehension-vocabulary-and-text-study.html": ("library-reading-comprehension-and-text-study.html", "Reading comprehension and text study"),
    "library-spelling-morphology-and-handwriting.html": ("library-spelling-and-morphology.html", "Spelling and morphology"),
    "library-mathematics.html": ("library-domain-maths.html", "Maths"),
}

# Areas whose page is organised by strand (a series per topic) instead of by type, keyed by area number.
# An entry joins a strand through its "strand" field, which must match a strand name here. Each strand is
# (name, one-sentence description, optional pointer to another area as (lead-in words, area number)).
# "intro" replaces the area's one-line description at the top of its page; "note" is shown under it.
# An area that is not listed here is laid out by type, as before.
STRANDS = {
    25: dict(
        intro="Some students keep finding reading, writing, maths or language hard, even when the teaching is good. I've gathered webinars, "
              "short videos, guides and research here to help you understand why, and what strong support looks like at Tier 1, Tier 2 and Tier 3. "
              "You'll also find webinars and guides, most of them Australian, on supporting students with ADHD, autistic students and other students with additional needs.",
        note="These resources are here to support your teaching. They are not a substitute for assessment or advice from a qualified "
             "professional, such as a psychologist, paediatrician or speech pathologist.",
        strands=[
            ("Understanding learning difficulties", "What learning difficulties and specific learning disorders are, how schools notice them through "
             "tiered support, and what reasonable adjustments look like.", ("For screening, intervention and the tiers across a whole school, see", 14)),
            ("Developmental language disorder", "A common and often hidden condition that makes understanding and using language hard, and what teachers can do "
             "alongside speech pathologists.", None),
            ("Dyslexia", "Persistent difficulty with accurate and fluent word reading and spelling, and the teaching and intervention that the evidence supports.", None),
            ("Dysgraphia and written expression", "Difficulties with handwriting, spelling and getting ideas onto the page, and how to teach and support each one.", None),
            ("Dyscalculia and maths difficulties", "Persistent difficulty with number and calculation, how it differs from gaps in what has been taught, "
             "and what effective maths intervention involves.", None),
            ("ADHD", "These are the webinars and guides I'd share with a teacher who wants to understand attention and motivation, "
             "and to set up a calm classroom where students with ADHD can do well. A few are made for families, and say so.", None),
            ("Autism", "Here you'll find webinars and classroom guides, most of them Australian, on communication, sensory needs, visual schedules and transitions, "
             "with autistic voices alongside the research.", None),
            ("Supporting students with additional needs", "I've gathered the practical things here, including what the Disability Standards ask of us, "
             "how to plan adjustments and Individual Education Plans, and how to work well with education support staff.", None),
            ("Related needs", "Working memory and coordination difficulties, which often sit alongside the learning difficulties above.", None),
        ]),
}
STRANDS[33] = dict(
    intro="Good literacy teaching rests on a handful of big ideas about how children learn to read, write and use language. "
          "I've gathered the frameworks and the research behind them here, so you can see where our practice comes from and explain it with confidence.",
    strands=[
        ("The Simple View of Reading", "Reading comprehension is the product of decoding and language comprehension, so a reader needs both, and a weakness in either one "
         "limits understanding. Philip Gough and William Tunmer proposed it in 1986, and Wesley Hoover and Gough set it out more fully in 1990.", None),
        ("Scarborough's Reading Rope", "Hollis Scarborough's picture of skilled reading as many strands, some for word recognition and some for language comprehension, "
         "woven together and strengthened through teaching and practice.", None),
        ("The Language House", "Pamela Snow pictures language and literacy as a house. The solid ground is the warm, responsive relationships of a child's first two years, and the "
         "foundations are the oral language built across the first five. Two walls rise together and hold each other up, with reading, writing and spelling on one side and the "
         "language skills for getting along with others on the other. Social and emotional wellbeing and social cognition form the rafter, and the roof is a young person's way into further education, "
         "training and work.", None),
        ("The Writing Rope and views of writing", "Joan Sedita's Writing Rope sorts the skills of writing into five strands, which are critical thinking, syntax, text structure, "
         "writing craft and transcription. The Simple and Not So Simple Views of Writing explain how handwriting and spelling, composing and self-regulation share a writer's "
         "limited working memory.", ("For teaching writing day to day, see", 10)),
        ("The Big Six and the five components", "The National Reading Panel named five components of reading instruction, which are phonemic awareness, phonics, fluency, "
         "vocabulary and comprehension. Deslea Konza added oral language and early literacy experiences to give Australian schools the Big Six.", None),
        ("How word reading develops", "How children move from sounding out to recognising words instantly, including Ehri's phases, orthographic mapping and what brain research shows.",
         ("For teaching it, see", 27)),
        ("Syntheses of the field", "The major reviews, inquiries and reports that pull the reading research together, from Australia's 2005 National Inquiry and England's Rose "
         "Review to Ending the Reading Wars. Structured literacy sits here too, meaning explicit, systematic and cumulative teaching of how language works, from sounds and "
         "spellings through to word parts, sentences and meaning.", None),
        ("Knowledge and comprehension", "Why reading comprehension is not one general skill, and how much a reader's knowledge of words and the world shapes what they understand.",
         ("For classroom practice, see", 30)),
        ("Oral language as the foundation", "Spoken language as the base that reading and writing are built on, and the Matthew effect, where early strengths or difficulties "
         "compound over time.", ("For classroom practice, see", 11)),
        ("Spelling and morphology", "Spelling draws on language knowledge, not visual memory alone. Good spellers draw on sounds, letter patterns and meaningful word parts together.",
         ("For classroom practice, see", 31)),
    ])
STRAND_ORDER = ("learn", "watch", "read", "research", "listen")   # within a strand: webinars first, then by type


def strands_of(x):
    """An entry's strands as a list. "strand" is one name, or a list of names when the entry sits in two strand areas
    (say Dyslexia in learning difficulties and Spelling and morphology in the frameworks area)."""
    s = x.get("strand")
    return [] if not s else (list(s) if isinstance(s, list) else [s])

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


def stack_of(x):
    """The Substack (from substacks.json) a Read entry was published on, matched by web address, or None."""
    if x["type"] != "read":
        return None
    host = domain_of(x["url"])
    return next((s for s in SUBSTACKS if domain_of(s["url"]) == host), None)


def source_of(x):
    """Who to file an entry under in the Source filter. A Learn session by 'Host, with Presenter' is filed under the host;
    a Substack post on Read is filed under its publication ("Filling the Pail"), so one menu choice finds all of it."""
    if x["type"] == "learn":
        return x["by"].split(", with ")[0]
    stack = stack_of(x)
    return stack["title"] if stack else x["by"]


def access_of(x):
    return next((t for t in ("Free account needed", "Check cost") if t in x["tags"]), "Free")


def domains_of(x):
    """The topics an entry belongs to, through its areas of practice, in the library's order."""
    return [d for d in DOMAIN_ORDER if any(AREA[n]["domain"] == d for n in x["areas"])]


def kind_label(x):
    return KIND_LABEL.get(x.get("kind"), "")


def search_words(x):
    """Extra words an entry should be found by. Maths is the site's one name for the topic, so the other two names are added."""
    words = "maths mathematics numeracy" if "Maths" in domains_of(x) else ""
    return words + (" times tables" if 35 in x["areas"] else "")   # number facts are what many teachers call times tables


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


def stack_for_url(url):
    """The Substack (from substacks.json) a web address belongs to, or None."""
    host = domain_of(url)
    return next((s for s in SUBSTACKS if domain_of(s["url"]) == host), None)


def read_thumb(url, img, name):
    """The picture across the top of a reading card: the article's own lead image, linked from the creator's server and
    never copied. Behind it sits a pale blue tile with the publication's name, which shows when there is no image or it
    fails to load (the image is then removed), so a card never shows a broken picture or loses its shape."""
    pic = ('<img src="%s" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="600" height="338" '
           'onerror="this.remove()">' % ea(img)) if img else ""
    # A square or upright image (Substack keeps the size in the file name, "_1024x1024.png") is often a title card with
    # words on it, so it is shown whole on pale blue rather than cropped to the wide frame.
    size = re.search(r"_(\d+)x(\d+)\.\w+$", unquote(img or ""))
    fit = "" if not img else (" lib-thumb-logo" if size and int(size.group(1)) < 1.3 * int(size.group(2)) else " lib-thumb-still")
    return ('<a class="lib-thumb lib-thumb-read%s" href="%s" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">'
            '<span class="lib-thumb-name">%s</span>%s</a>' % (fit, ea(url), e(name), pic))


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
        text = " ".join([x["title"], x["by"], x.get("summary", ""), x.get("focus", ""), " ".join(x["meta"]), kind_label(x), search_words(x)]
                        + [AREA[n]["name"] for n in x["areas"]] + domains_of(x)).lower()
        if x["type"] == "listen":   # Listen keeps its categories
            data = ' data-topics="%s" data-areas="%s" data-by="%s" data-text="%s"' % (
                ea("|".join(topics_of(x))), ",".join(str(n) for n in x["areas"]), ea(source_of(x)), ea(text))
        else:                       # Watch and Learn: topic, area of practice and kind
            data = ' data-domain="%s" data-areas="%s" data-kind="%s" data-by="%s" data-text="%s"' % (
                ea("|".join(domains_of(x))), ",".join(str(n) for n in x["areas"]), ea(kind_label(x)), ea(source_of(x)), ea(text))
        if x["type"] == "watch":
            data += ' data-bands="%s" data-subject="%s"' % (",".join(x.get("bands", [])), ea(x.get("subject", "")))
        if x["type"] == "learn":
            data += ' data-length="%s" data-audience="%s" data-access="%s"' % (ea(x.get("length") or NO_LENGTH), ea(x.get("audience", "")), ea(access_of(x)))
    thumb = ""
    stack = stack_of(x)
    read_top = x["type"] == "read" and READ_PICTURE == "top"
    if x["type"] in ("watch", "learn"):
        img = THUMBS.get(x["url"])
        pic = ('<img src="%s" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="480" height="270" '
               'onerror="this.remove()">' % ea(img)) if img else ""
        kind = "" if not img else (" lib-thumb-still" if any(h in img for h in STILL_HOSTS) else " lib-thumb-logo")
        thumb = ('<a class="lib-thumb%s" href="%s" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">'
                 '<span class="lib-thumb-name">%s</span>%s<span class="lib-thumb-play"></span></a>' % (kind, ea(x["url"]), e(x["by"] or domain_of(x["url"])), pic))
        # What kind of video it is, shown on the corner of the picture. It is real text (the picture link is hidden from
        # screen readers, so the label sits outside it) and reads before the title.
        thumb += '<p class="lib-kind lib-kind-%s">%s</p>' % (x["type"], e(kind_label(x)))
    elif read_top:
        # The article's lead image across the top of the card (no play button). Without one, or if it fails to load,
        # the tile shows the publication or source on pale blue, so every card in a row lines up.
        thumb = read_thumb(x["url"], THUMBS.get(x["url"]), stack["title"] if stack else (x["by"] or domain_of(x["url"])))
    if line and BYLINE_ICON and stack and stack.get("icon"):
        line = ('<img class="lib-by-icon" src="%s" alt="" width="20" height="20" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
                'onerror="this.remove()">%s' % (ea(stack["icon"]), line))
    head = '%s%s<%s class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></%s>%s' % (
        badge, focus, level, ea(x["url"]), title_html(x["title"]), NEWTAB, level, ('<p class="lib-by">%s</p>' % line) if line else "")
    # A small picture beside the heading: the show's cover art on episodes, the page's own preview image on research and
    # curriculum (and on reading when READ_PICTURE is "side").
    # Linked from the creator's server, never copied; if it fails to load it is removed and the card reads as plain text.
    side_types = ("research", "curriculum") if read_top else ("read", "research", "curriculum")
    side = SHOW_ART.get(x["by"]) if x["type"] == "listen" else (THUMBS.get(x["url"]) if x["type"] in side_types else None)
    if side:
        w, h = (56, 56) if x["type"] == "listen" else (64, 64)
        head = ('<div class="lib-card-head"><img class="lib-card-pic%s" src="%s" alt="" width="%d" height="%d" loading="lazy" decoding="async" '
                'referrerpolicy="no-referrer" onerror="this.remove()"><div>%s</div></div>' % (" lib-card-art" if x["type"] == "listen" else " lib-card-side", ea(side), w, h, head))
    return (
        '<article class="lib-card%s" data-type="%s"%s>%s%s'
        '%s%s<p class="lib-card-foot">%s<span class="lib-source">Opens at %s</span></p></article>'
        % (" has-thumb" if thumb else "", x["type"], data, thumb, head, summary, topics, tags, e(domain_of(x["url"])))
    )


MIX_TYPES = ("watch", "learn", "listen", "read")
# A numbered part of a series: "... episode 3", "... Part 2", "... session 4", or "Title, #3: ..." (Greg Ashman's
# "Five arguments against explicit teaching, #1" to "#5"). A bare "#49" with no comma before it (Craig Barton's
# "Tip #49", "Research Bite #56") is not a series: each of those is a separate piece on its own topic.
_SERIES = re.compile(r"^(.*?)(?:[,:]?\s+(?:episode|part|session)\s+\d+|,\s*#\d+)", re.I)


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


def field(fid, label, key, opts, all_label, extra=""):
    return ('<div class="lib-field%s"><label for="%s">%s</label><select id="%s" data-filter="%s">%s</select></div>'
            % (extra, fid, e(label), fid, key, options(opts, all_label)))


def shelf_menus(items, kind):
    """The menus on Watch, Learn and Read: "Topic", then "Area of practice", which lists only the areas inside the chosen topic.
    A topic or an area is offered only when this shelf has at least one entry for it, so every choice finds something.
    The other menus follow, with the less used ones under "More filters". Without JavaScript the list simply shows in full."""
    topics = [d for d in DOMAIN_ORDER if any(d in domains_of(x) for x in items)]
    areas = [a for a in AREAS if any(a["n"] in x["areas"] for x in items)]
    main = [field("fTopic", "Topic", "domain", [(d, d) for d in topics], "All topics")]
    # Every area is written out with its topic; filter.js keeps only the chosen topic's areas in the menu.
    main.append('<div class="lib-field"><label for="fArea">Area of practice</label><select id="fArea" data-filter="areas" disabled>'
                '<option value="">Choose a topic first</option>%s</select></div>'
                % "".join('<option value="%d" data-domain="%s">%s</option>' % (a["n"], ea(a["domain"]), e(a["name"])) for a in areas))
    kinds = [l for l in KIND_LABEL.values() if any(kind_label(x) == l for x in items)]
    more = []
    if kind == "read":
        main.append(publication_field(items))
        access = [v for v in ["Free", "Free account needed", "Check cost"] if any(access_of(x) == v for x in items)]
        if len(access) > 1:
            more.append(field("fAccess", "Access", "access", [(v, v) for v in access], "Any"))
    elif kind == "watch":
        main.append(field("fBand", "Year level", "bands", [("F-2", "Foundation to Year 2"), ("3-6", "Years 3 to 6"), ("Secondary", "Secondary")],
                          "All year levels", " lib-field-extra"))
        main.append(field("fKind", "What you will see", "kind", [(k, k) for k in kinds], "Any kind of video", " lib-field-extra"))
        subjects = [v for v in ["Literacy and English", "Maths", "Across subjects", "Other subjects"] if any(x.get("subject") == v for x in items)]
        more.append(field("fSubject", "Lesson subject", "subject", [(v, v) for v in subjects], "All subjects"))
    else:
        main.append(field("fKind", "Format", "kind", [(k, k) for k in kinds], "Any format", " lib-field-extra"))
        lengths = [v for v in LENGTHS + [NO_LENGTH] if any((x.get("length") or NO_LENGTH) == v for x in items)]
        main.append(field("fLength", "Length", "length", [(v, v) for v in lengths], "Any length", " lib-field-extra"))
        audiences = sorted(set(x.get("audience") for x in items if x.get("audience")))
        more.append(field("fAudience", "Made for", "audience", [(v, v) for v in audiences], "Everyone"))
        access = [v for v in ["Free", "Free account needed", "Check cost"] if any(access_of(x) == v for x in items)]
        more.append(field("fAccess", "Access", "access", [(v, v) for v in access], "Any"))
    if kind != "read":
        sources = sorted(set(source_of(x) for x in items if x["by"]), key=str.lower)
        more.append(field("fBy", "Source", "by", [(v, v) for v in sources], "All sources"))
    more.append('<div class="lib-field lib-field-wide"><label for="fText">Search within this page</label>'
                '<input type="search" id="fText" placeholder="e.g. worked examples" autocomplete="off"></div>')
    chips = "".join('<button type="button" class="lib-chip" data-topic="%s">%s <span>%d</span></button>'
                    % (ea(d), e(d), sum(1 for x in items if d in domains_of(x))) for d in topics)
    return ('<form class="lib-filters lib-filters-top" id="libFilters" aria-label="Filter this shelf"><div class="lib-filter-row lib-filter-main">%s</div>'
            '<details class="lib-morefilters" id="libMoreFilters"><summary>More filters</summary><div class="lib-filter-row">%s</div></details>'
            '<p class="lib-filter-status"><span id="fCount" role="status" aria-live="polite"></span> '
            '<button type="reset" class="lib-reset">Clear filters</button></p></form>'
            '<div class="lib-chips lib-chips-topics" id="libChips"><p>Browse by topic</p><div>%s</div></div>' % ("".join(main), "".join(more), chips))


def publication_field(items):
    """Read's "Publication or source" menu: the Substacks first (each holds that publication's key articles), then every
    other source. "See key articles" on a Substack card opens the shelf with this menu set (library-read.html?by=...)."""
    titles = set(source_of(x) for x in items if x["by"])
    stacks = sorted((s for s in SUBSTACKS if s["title"] in titles), key=lambda s: s["title"].lower())
    names = set(s["title"] for s in stacks)
    others = sorted(titles - names, key=str.lower)
    def opt(v, label):
        return '<option value="%s">%s</option>' % (ea(v), e(label))
    label = lambda s: s["title"] if s["by"] == s["title"] or s["by"] in s["title"] else "%s (%s)" % (s["title"], s["by"])
    return ('<div class="lib-field lib-field-extra"><label for="fBy">Publication or source</label><select id="fBy" data-filter="by">'
            '<option value="">All publications and sources</option><optgroup label="Substacks">%s</optgroup><optgroup label="Other sources">%s</optgroup>'
            '</select></div>' % ("".join(opt(s["title"], label(s)) for s in stacks), "".join(opt(v, v) for v in others)))


def shelf_order(items):
    """A shelf's cards in order: by the first area of practice each is tagged with, topic by topic, with a numbered series
    kept together where its first part belongs and the sources spread out inside each area."""
    order = {a["n"]: i for i, a in enumerate(AREAS)}
    area_rank = lambda x: (order.get(x["areas"][0], 99) if x["areas"] else 99)
    lead = {}
    for x in items:
        m = _SERIES.match(x["title"])
        if m:
            lead.setdefault((x["by"], m.group(1).lower()), area_rank(x))
    def rank(x):
        m = _SERIES.match(x["title"])
        return lead[(x["by"], m.group(1).lower())] if m else area_rank(x)
    items = sorted(items, key=rank)
    return [x for _, run in itertools.groupby(items, key=rank) for x in mix(list(run))]


def not_first(items, kind):
    """On Read, a writer in NOT_FIRST_ON_READ does not open a list: the first card by someone else is moved to the front."""
    lead = lambda x: any(name in x["by"] for name in NOT_FIRST_ON_READ)
    if kind != "read" or not items or not lead(items[0]):
        return items
    i = next((i for i, x in enumerate(items) if not lead(x)), None)
    return items if i is None else [items[i]] + items[:i] + items[i + 1:]


def shelf_list(items, kind):
    """The full list of a Watch or Learn shelf, 24 cards at a time, with its "Show more" button and empty state."""
    t = TYPES[kind]
    other = TYPES[{"watch": "learn", "learn": "watch", "read": "research"}[kind]]
    hint = ("look on the <a href=\"%s\">%s shelf</a> for %s on the same topic" % (other["page"], other["label"],
            {"watch": "webinars, talks and explainers", "learn": "lessons being taught", "read": "papers and reviews"}[kind]))
    return ('<div id="libList">%s</div>' % cards(not_first(shelf_order(items), kind), False, "h3", True, mixed=False)
            + '<p class="lib-more" hidden><button type="button" class="btn btn-primary" id="libMore">Show more</button></p>'
            + '<p class="lib-empty" id="libEmpty" hidden>No %s match those choices yet. Try clearing one of the menus, or %s. '
            'If you know something that belongs here, <a href="%s">email a suggestion</a>. '
            '<button type="reset" form="libFilters" class="lib-reset">Clear filters</button></p>' % (t["short"], hint, SUGGEST)
            + '<script src="library/filter.js?v=6" defer></script>')


def filter_bar(items, kind):
    """Filter controls for the Listen list. Works without JavaScript as a plain list."""
    area_ns = [a["n"] for a in AREAS if any(a["n"] in x["areas"] for x in items)]
    topic_names = [t for t in TOPICS if any(t in topics_of(x) for x in items)]
    fields = ['<div class="lib-field"><label for="fTopic">Category</label><select id="fTopic" data-filter="topics">%s</select></div>'
              % options([(t, t) for t in topic_names], "All categories")]
    fields += ['<div class="lib-field"><label for="fArea">Focus area</label><select id="fArea" data-filter="areas">%s</select></div>'
              % options([(str(n), short_area(n)) for n in area_ns], "All focus areas")]
    by_label = "Show"
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
    items = shelf_order(items)
    return (filter_bar(items, kind) + '<div id="libList">%s</div>' % cards(items, False, "h3", True, mixed=False)
            + '<p class="lib-more" hidden><button type="button" class="btn btn-primary" id="libMore">Show more</button></p>'
            + '<p class="lib-empty" id="libEmpty" hidden>Nothing matches those filters yet. Try clearing one, or <a href="%s">email a suggestion</a>. '
            '<button type="reset" form="libFilters" class="lib-reset">Clear filters</button></p>' % SUGGEST
            + '<script src="library/filter.js?v=6" defer></script>')


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


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
FEATURED_INTRO = "Three free pieces I think are worth your time this week. Each one opens on the writer's own Substack."


def featured_week():
    """featured.json's week as a date, or None when the panel should not show: no file, no items, a bad date,
    or a week that began more than FEATURED_DAYS days ago (KN_TODAY=YYYY-MM-DD stands in for today, for testing)."""
    items = [x for x in FEATURED.get("items") or [] if x.get("url") and x.get("title")]
    try:
        week = date.fromisoformat(FEATURED.get("week_of", ""))
    except (TypeError, ValueError):
        return None
    today = date.fromisoformat(os.environ["KN_TODAY"]) if os.environ.get("KN_TODAY") else date.today()
    return week if items and (today - week).days <= FEATURED_DAYS else None


def featured_panel(where):
    """"This week's reading": the three picks in featured.json, on the home page (where="home") and at the top of Read.
    Left out of the page when featured_week() says so. The page is not rebuilt every day, so a short script straight after
    the panel also hides it (and the Read page's jump link to it) once the week is more than FEATURED_DAYS days old."""
    week = featured_week()
    if not week:
        return ""
    when = "Week of %d %s %d" % (week.day, MONTHS[week.month - 1], week.year)
    level = "h3"
    def pic(x):   # the article's lead image (recorded by feature_week.py), or the publication's name on pale blue
        stack = stack_for_url(x["url"])
        return read_thumb(x["url"], x.get("image") or THUMBS.get(x["url"]), stack["title"] if stack else (x.get("by") or domain_of(x["url"])))
    cards_html = "".join(
        '<article class="lib-card has-thumb kn-week-card">%s<%s class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></%s>'
        '<p class="lib-by">%s</p>%s<p class="lib-card-foot"><span class="lib-source">Opens at %s in a new tab</span></p></article>'
        % (pic(x), level, ea(x["url"]), title_html(x["title"]), NEWTAB, level, e(x.get("by", "")),
           ('<p class="lib-summary kn-week-why">%s</p>' % e(x["why"])) if x.get("why") else "", e(domain_of(x["url"])), )
        for x in FEATURED["items"] if x.get("url") and x.get("title"))
    intro = e(FEATURED.get("intro") or FEATURED_INTRO)
    hide = ('<script>(function(){var s=document.getElementById("this-week");if(!s)return;'
            'var w=new Date(s.getAttribute("data-week")+"T00:00:00+11:00").getTime();'
            'if(isNaN(w)||Date.now()-w>%d*864e5){s.hidden=true;var a=document.querySelector(\'a[href="#this-week"]\');if(a)a.hidden=true;}})();</script>' % (FEATURED_DAYS + 1))
    if where == "home":
        return ('<section class="section kn-week-home" id="this-week" data-week="%s" aria-labelledby="this-week-title"><div class="container">'
                '<div class="section-header"><p class="kn-eyebrow">%s</p><h2 id="this-week-title">This week\'s reading</h2><p>%s</p></div>'
                '<div class="kn-week-grid">%s</div><p class="kn-week-more"><a href="library-read.html">More to read on the Read shelf %s</a></p></div></section>%s'
                % (week.isoformat(), when, intro, cards_html, ARROW, hide))
    return ('<section class="kn-week" id="this-week" data-week="%s" aria-labelledby="this-week-title"><p class="kn-eyebrow">%s</p>'
            '<h2 id="this-week-title">This week\'s reading</h2><p class="kn-week-intro">%s</p><div class="kn-week-grid">%s</div></section>%s'
            % (week.isoformat(), when, intro, cards_html, hide))


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
    "Literacy": "Oral language, phonological awareness, phonics, fluency, vocabulary, comprehension, spelling, handwriting and writing, with the research behind them.",
    "Maths": "Clear, evidence-informed maths teaching from the early years up.",
    "Knowledge-rich curriculum": "Sequencing knowledge so learning builds, within and across subjects.",
    "MTSS and assessment": "Screening, assessment and tiered support, including for students with learning difficulties, disorders and additional needs.",
    "Coaching and professional learning": "Instructional coaching and professional learning that changes practice.",
    "Leadership and culture": "Instructional leadership, school culture, behaviour and strong teams.",
    "Implementation and change": "Putting good ideas into practice, and bringing people with you.",
    "Research and evidence": "Reading the evidence, weighing the debates and spotting the myths.",
}


# What a domain covers, shown as chips on its page. These are elements of understanding, not separate pages.
DOMAIN_ELEMENTS = {
    "MTSS and assessment": ["Tier 1: strong teaching for all", "Tier 2: targeted support", "Tier 3: intensive support",
                            "Screening", "Progress monitoring", "Assessment and data", "Learning difficulties and disorders",
                            "ADHD, autism and additional needs"],
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
    popular = [2, 27, 10, 16, 17, 4]
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
    body += ('<section class="section" id="types"><div class="container"><div class="section-header"><p class="kn-eyebrow">%d resources, each linked to its creator</p><h2>Browse the library</h2>'
             '<p>Know how you want to learn today? Pick a shelf.</p></div>%s</div></section>' % (len(ENTRIES), type_tiles()))
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
    body += '<script src="library/search.js?v=8" defer></script>'
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


# "Start with these three" on Watch: the start of three titles, from different creators and areas. Change them here.
WATCH_START = ["Explicit phonics instruction: modelled and guided practice", "Chalk Dust S1 E4", "Rebecca Sloots"]
TOPIC_SECTION_MIN = 10   # a topic gets its own section on a shelf when the shelf has this many entries for it


def lower_first(name):
    """"Literacy" -> "literacy", but "MTSS and assessment" keeps its capitals."""
    return name if name.split()[0].isupper() else name[0].lower() + name[1:]


def shelf_link(kind, domain, area=None):
    """A link that opens a shelf with the Topic (and Area of practice) menus already set. filter.js applies it without a reload."""
    href = "%s?domain=%s" % (TYPES[kind]["page"], domain.replace(" ", "+"))
    return ea(href + ("&areas=%d" % area if area else ""))


def staff_card(x):
    return ('<article class="lib-card lib-staff"><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3>'
            '<p class="lib-by">%s</p><p class="lib-start-label">Talk about it afterwards</p><ul>%s</ul>'
            '<p class="lib-card-foot"><span class="lib-source">Opens at %s</span></p></article>'
            % (ea(x["url"]), title_html(x["title"]), NEWTAB, " &middot; ".join(e(b) for b in [x["by"]] + shown_meta(x) if b),
               "".join("<li>%s</li>" % e(q) for q in x["staff"]), e(domain_of(x["url"]))))


def featured_strip(items, kind):
    """The short strip under the menus: three places to start on Watch, three staff sessions on Learn."""
    def li(x):   # a link list, so no bold lead-in
        return ('<li><span class="lib-kind-inline lib-kind-%s">%s</span> <a href="%s" target="_blank" rel="noopener">%s%s</a> <span class="lib-featured-by">%s</span></li>'
                % (x["type"], e(kind_label(x)), ea(x["url"]), e(x["title"]), NEWTAB, e(x["by"])))
    if kind == "read":   # Read opens with "This week's reading" instead (featured_panel)
        return ""
    if kind == "watch":
        picks = [x for p in WATCH_START for x in items if cap_after_colon(x["title"]).lower().startswith(cap_after_colon(p).lower())]
        if not picks:
            return ""
        return ('<section class="lib-featured lib-browse" id="start"><h2>New to this shelf? Start with these three</h2>'
                '<ul class="lib-featured-list">%s</ul></section>' % "".join(li(x) for x in picks[:3]))
    staff = [x for x in items if x.get("staff")]
    if not staff:
        return ""
    return ('<section class="lib-featured lib-browse" id="staff"><h2>Run it as a staff session</h2><p>Recordings that suit a whole-staff meeting, '
            'each with a couple of prompts to get the conversation going.</p><ul class="lib-featured-list">%s</ul>'
            '<details class="lib-expand"><summary>Show all %d staff sessions with their prompts</summary><div class="lib-grid">%s</div></details></section>'
            % ("".join(li(x) for x in staff[:3]), len(staff), "".join(staff_card(x) for x in staff)))


def topic_sections(items, kind):
    """One section for each big topic on the shelf: its count, its areas of practice with their counts, three sample cards
    from different creators and a link to see the rest. Smaller topics are listed in one line at the end. Every link here
    sets the menus above, and the sections make way for the list of matching cards."""
    t = TYPES[kind]
    ordered = shelf_order(items)
    out, small = "", []
    for d in DOMAIN_ORDER:
        sub = [x for x in ordered if d in domains_of(x)]
        if not sub:
            continue
        if len(sub) < TOPIC_SECTION_MIN:
            small.append('<a href="%s" data-set>%s <span class="lib-count">%d</span></a>' % (shelf_link(kind, d), e(d), len(sub)))
            continue
        areas = [(a, sum(1 for x in sub if a["n"] in x["areas"])) for a in AREAS if a["domain"] == d]
        links = "".join('<a href="%s" data-set>%s <span class="lib-count">%d</span></a>' % (shelf_link(kind, d, a["n"]), e(a["name"]), n)
                        for a, n in areas if n) if len([1 for a, n in areas if n]) > 1 else ""
        # Three samples: different creators, different areas where possible, and ones with a picture first.
        picks = []
        for strict in (True, False):
            for x in sorted(sub, key=lambda x: 0 if THUMBS.get(x["url"]) else 1):
                if len(picks) == 3:
                    break
                if x in picks or any(x["by"] == y["by"] for y in picks):
                    continue
                if strict and any(set(x["areas"]) & set(y["areas"]) for y in picks):
                    continue
                picks.append(x)
        out += ('<section class="lib-topic lib-browse" id="t-%s"><div class="lib-topic-head"><h2>%s <span class="lib-count">%d</span></h2>'
                '<a class="lib-seeall" href="%s" data-set>See all %d %s %s %s</a></div>%s%s</section>'
                % (domain_slug(d), title_html(d), len(sub), shelf_link(kind, d), len(sub), e(lower_first(d)), t["short"], ARROW,
                   ('<p class="lib-topic-areas">%s</p>' % links) if links else "", cards(not_first(picks, kind), False, "h3", mixed=False)))
    if small:
        out += '<p class="lib-topic-more lib-browse">%s%s</p>' % (label_html("More topics on this shelf:"), "".join(small))
    return out


def shelf_page(items, kind):
    """Watch and Learn, top to bottom: the menus, the topic buttons, a short featured strip, a section for each big topic,
    then the full list. As soon as a menu, button or the search box is used, the strip and the topic sections make way
    and the list shows only what matches."""
    t = TYPES[kind]
    lead = ""
    if kind == "learn":
        lead = ('<p class="lib-group-lead">Sessions marked "Free account needed" open on the host\'s page, where a free sign-in unlocks the recording. '
                'If a webinar or recorded session has shaped your thinking, <a href="mailto:%s?subject=Learn%%20suggestion">send it my way</a>.</p>' % EMAIL)
    elif kind == "read":
        lead = ('<p class="lib-group-lead">Everything on this shelf is free to read. From the Substacks I follow most closely I\'ve picked out key free posts '
                'and filed them by topic, alongside articles and guides from across the web.</p>')
    return (shelf_menus(items, kind) + featured_strip(items, kind) + topic_sections(items, kind)
            + '<section class="lib-group lib-all" id="all"><h2 id="libListHeading" tabindex="-1" data-all="All %s" data-some="Matching %s">'
              '<span id="libListLabel">All %s</span> <span class="lib-count" id="libListCount">%d</span></h2>%s%s</section>'
              % (t["short"], t["short"], t["short"], len(items), lead, shelf_list(items, kind)))


def build_types():
    for key, t in TYPES.items():
        items = [x for x in ENTRIES if x["type"] == key]
        lead = e(t["blurb"]) + " Every entry links to the original."
        intro = outro = ""
        hero_jump = ""
        if key in ("voice", "curriculum"):
            items = sorted(items, key=lambda x: x["title"].lower())
            nav, sections = [], '<section class="lib-group">%s</section>' % cards(items, False, "h2")
        elif key in ("watch", "learn", "read"):
            nav = []
            lead = e(t.get("promise", t["blurb"])) + " Every entry links to the original."
            if t.get("cross"):
                hero_jump = '<p class="lib-cross">%s <a href="%s">%s</a>.</p>' % (e(t["cross"][0]), t["cross"][2], e(t["cross"][1]))
            sections = shelf_page(items, key)
        elif key == "listen":
            nav = []
            sections = ('<section class="lib-group" id="all"><h2>Episodes by category <span class="lib-count">%d</span></h2><p class="lib-group-lead">'
                        "Looking for something specific? Use the categories and search below to find episodes on the topic you're working on.</p>%s</section>"
                        % (len(items), filtered_list(items, key)))
        elif key == "research":
            nav, sections = domain_sections(items)
        else:
            nav, sections = grouped_sections(items)
        if key == "read":
            intro = featured_panel("read")
            nav = ([("this-week", "This week's reading")] if intro else []) + [("all", "All articles"), ("substacks", "Substacks worth following")]
        if key == "read" and SUBSTACKS:
            def stack_card(x):
                pace = "Posts most weeks" if x["n365"] >= 20 else ("A couple of posts a month" if x["n365"] >= 10 else "Posts now and then")
                # "See key articles" sets the Publication menu above (filter.js), or opens the shelf with it set when followed from elsewhere.
                n = sum(1 for y in items if source_of(y) == x["title"])
                keys = ('<p class="lib-stack-keys"><a href="%s" data-set>See key articles <span class="lib-count">%d</span></a></p>'
                        % (ea("library-read.html?by=" + quote_plus(x["title"])), n)) if n else ""
                # The publication's own icon (its Substack logo, loaded from Substack's image server), or its initial when it has none.
                # The initial sits behind the picture, so it shows if the picture fails to load (the picture is then removed).
                pic = ('<img src="%s" alt="" width="56" height="56" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">'
                       % ea(x["icon"])) if x.get("icon") else ""
                icon = '<span class="lib-stack-icon lib-show-initial" aria-hidden="true">%s%s</span>' % (e(re.sub(r"^Dr\.? ", "", x["title"])[:1]), pic)
                who = " &middot; ".join(e(b) for b in [x["by"], REGION_SHORT.get(x["region"], x["region"])] if b)
                return ('<article class="lib-card lib-stack">%s<div><h3 class="lib-card-title"><a href="%s" target="_blank" rel="noopener">%s%s</a></h3><p class="lib-by">%s</p>'
                        '<p class="lib-summary">%s</p>%s<p class="lib-card-foot"><span class="lib-tag">%s</span><span class="lib-source">Opens at %s</span></p></div></article>'
                        % (icon, ea(x["url"]), title_html(x["title"]), NEWTAB, who, e(x["desc"]), keys, pace, e(domain_of(x["url"]))))
            must = [x for name in MUST_SUBSTACKS for x in SUBSTACKS if x["title"] == name]
            outro = ('<section class="lib-group lib-stacks" id="substacks"><h2>Substacks worth following <span class="lib-count">%d</span></h2>'
                     '<p class="lib-group-lead">Some of the best thinking in education now arrives by newsletter. These are free to subscribe to, though some writers keep '
                     'part of their work for paying subscribers. Where a Substack has "See key articles", I\'ve listed its key free posts on this shelf. '
                     'Know one that belongs here? <a href="mailto:%s?subject=Substack%%20suggestion">Send it my way</a>.</p>' % (len(SUBSTACKS), EMAIL))
            if must:
                outro += '<h3 class="lib-subhead">My must-follows</h3><div class="lib-grid">%s</div>' % "".join(stack_card(x) for x in must)
            # One list in SUBSTACK_ORDER (each card names its region); any Substack not in that list goes at the end.
            rank = {name: i for i, name in enumerate(SUBSTACK_ORDER)}
            rest = sorted((x for x in SUBSTACKS if x not in must), key=lambda x: rank.get(x["title"], len(rank)))
            if rest:
                outro += ('<h3 class="lib-subhead">More Substacks worth following</h3>' if must else "") + '<div class="lib-grid">%s</div>' % "".join(stack_card(x) for x in rest)
            outro += '</section>'
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
        body += '<section class="section lib-list"><div class="container">%s%s%s%s<div class="lib-end">%s</div></div></section>' % (toc, intro, sections, outro, suggest_box())
        write(t["page"], "%s | The Knowledge Nest Library" % t["title"],
              "%d %s in the free Knowledge Nest Library, chosen for teachers and school leaders. Every entry links to the original and names its creator." % (len(items), t["noun"]),
              body, t["title"])


# ---------- area pages ----------
def strand_id(name):
    return "strand-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def strand_sections(items, plan):
    """The main column of an area that is organised by strand: the note, a "Jump to" list of the strands, then one
    section per strand with its description, a count and its cards. Every card shows its type. Within a strand
    the order is Learn, Watch, Read, Research, Listen, with sources spread through each of those groups.
    Also returns an "On this page" box for the side column."""
    nav, out = [], ""
    for name, about, more in plan["strands"]:
        sub = [x for x in items if name in strands_of(x)]
        if not sub:
            continue
        nav.append((strand_id(name), name))
        ordered = [x for k in STRAND_ORDER for x in mix([y for y in sub if y["type"] == k])]
        ordered += [x for x in sub if x["type"] not in STRAND_ORDER]
        lead = e(about)
        if more:
            lead += ' %s <a href="%s">%s</a>.' % (e(more[0]), area_page(AREA[more[1]]), e(AREA[more[1]]["name"]))
        out += ('<section class="lib-group lib-strand-group" id="%s"><h2>%s <span class="lib-count">%d</span></h2><p class="lib-group-lead">%s</p>%s'
                '<p class="lib-backtop"><a href="#strands">Back to the list of strands <span aria-hidden="true">&uarr;</span></a></p></section>'
                % (strand_id(name), title_html(name), len(sub), lead, cards(ordered, True, mixed=False)))
    links = "".join('<a href="#%s">%s</a>' % (i, e(l)) for i, l in nav)
    top = ('<p class="lib-note">%s</p>' % e(plan["note"])) if plan.get("note") else ""
    top += '<nav class="lib-toc lib-toc-wrap" id="strands" aria-label="Strands on this page">%s%s</nav>' % (label_html("Jump to:"), links)
    side = ('<nav class="lib-side-box lib-side-toc" aria-label="On this page"><h2>On this page</h2><ul>%s</ul></nav>'
            % "".join('<li><a href="#%s">%s</a></li>' % (i, e(l)) for i, l in nav))
    return top + out, side


def build_areas():
    grouped = by_area(ENTRIES)
    for a in AREAS:
        items = grouped.get(a["n"], [])
        if not items:
            continue
        present = [k for k in TYPES if any(x["type"] == k for x in items)]
        plan = STRANDS.get(a["n"])
        chips = ('<p class="lib-practices">%s%s</p>' % (label_html("Practices in this area:"), "".join("<em>%s</em>" % e(p[0].upper() + p[1:]) for p in a["practices"]))) if a["practices"] else ""
        body = hero(a["domain"], a["name"], e(plan["intro"] if plan else a["about"]), crumbs=[("Library", "library.html"), (a["domain"], domain_page(a["domain"], {n: len(v) for n, v in grouped.items()}) if len(domain_areas(a["domain"], {n: len(v) for n, v in grouped.items()})) > 1 else "library.html#areas"), (a["name"], None)],
                    extra=chips + ("" if plan else jump([(k, TYPES[k]["label"]) for k in present])))
        sections, strand_nav = "", ""
        if plan:
            sections, strand_nav = strand_sections(items, plan)
        for k in ([] if plan else present):
            sub = [x for x in items if x["type"] == k]
            sections += '<section class="lib-group" id="%s"><h2>%s <span class="lib-count">%d</span></h2>%s</section>' % (k, TYPES[k]["label"], len(sub), cards(sub, False))
        related = "".join('<li><a href="%s">%s</a></li>' % (area_page(b), e(b["name"])) for b in AREAS
                          if b["domain"] == a["domain"] and b["n"] != a["n"] and grouped.get(b["n"]))
        side = strand_nav
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


def build_stubs():
    """A small page at each retired address saying where the page went. It is marked noindex, names the new page as its
    canonical address, sends the browser on after a moment and is left out of the sitemap and the search index."""
    for name, (target, label) in RETIRED_PAGES.items():
        assert os.path.exists(os.path.join(ROOT, target)), "the page that replaces %s was not built: %s" % (name, target)
        body = ('<section class="page-hero lib-hero"><div class="container page-hero-inner"><div class="page-hero-text lib-hero-text">'
                '<p class="hero-tagline">Library</p><h1>This page has moved</h1>'
                '<p class="page-hero-lead">This page has moved to <a href="%s">%s</a>. You will be taken there in a moment.</p>'
                '</div></div></section>' % (target, e(label)))
        write(name, "This page has moved | The Knowledge Nest Library", "This page has moved to %s." % label, body)
        BUILT.remove(name)   # so it stays out of the sitemap
        path = os.path.join(ROOT, name)
        page = open(path, encoding="utf8").read()
        page = page.replace("<head>", '<head>\n  <meta name="robots" content="noindex">\n  <meta http-equiv="refresh" content="3; url=%s">' % target, 1)
        page = page.replace('<link rel="canonical" href="%s' % public(name), '<link rel="canonical" href="%s' % public(target), 1)
        page = page.replace('<meta property="og:url" content="%s' % public(name), '<meta property="og:url" content="%s' % public(target), 1)
        assert 'noindex' in page and 'rel="canonical" href="%s"' % public(target) in page, name
        open(path, "w", encoding="utf8").write(page)


def build_home_block():
    """Refreshes the library sections on the site's home page, between the LIBRARY markers."""
    path = os.path.join(ROOT, "index.html")
    src = open(path, encoding="utf8").read()
    start, end = "<!-- LIBRARY:START (generated by library/build.py, do not edit by hand) -->", "<!-- LIBRARY:END -->"
    if start not in src or end not in src:
        return
    block = (featured_panel("home") +
             '<section class="section" id="types"><div class="container"><div class="section-header"><p class="kn-eyebrow">%d resources, each linked to its creator</p><h2>Browse the library</h2>'
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
        if kind_label(x):
            row["k"] = kind_label(x)
        words = " ".join(v for v in [x.get("focus", ""), " ".join(strands_of(x)), x.get("summary", ""), " ".join(domains_of(x)), search_words(x)] if v)   # searched, not shown
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
    prose += [("strand text '%s'" % name, text) for plan in STRANDS.values() for name, text, _ in plan["strands"]]
    prose += [("%s of the strands for area %d" % (k, n), plan.get(k, "")) for n, plan in STRANDS.items() for k in ("intro", "note")]
    prose += [("featured.json why line for '%s'" % x.get("title"), x.get("why", "")) for x in FEATURED.get("items") or []]
    prose += [("featured.json intro", FEATURED.get("intro", ""))]
    for where, text in prose:
        if text and _COLON.sub(_cap, text) != text:
            out.append("colon before a lower-case word in the %s: %s" % (where, text))
    if not featured_week():
        out.append("This week's reading is left out: featured.json is missing, has no picks or is more than %d days old (week_of %r). "
                   "Set this week's picks with library/tools/feature_week.py" % (FEATURED_DAYS, FEATURED.get("week_of")))
    for x in FEATURED.get("items") or []:
        if "\u2014" in x.get("why", ""):
            out.append("featured.json why line for '%s' has an em dash; reword" % x.get("title"))
    for s in SUBSTACKS:
        if s["title"] not in SUBSTACK_ORDER and s["title"] not in MUST_SUBSTACKS:
            out.append("Substack '%s' is not in SUBSTACK_ORDER in build.py, so it is listed last; add it where it belongs" % s["title"])
    for t in START_HERE:
        for p in t["picks"]:
            if not any(cap_after_colon(x["title"]).startswith(cap_after_colon(p)) for x in ENTRIES):
                out.append("Start here pick '%s' (%s) matches no title, so another entry is shown in its place" % (p, t["title"]))
    for n, plan in STRANDS.items():
        names = [s[0] for s in plan["strands"]]
        for x in ENTRIES:
            if n in x["areas"] and not set(strands_of(x)) & set(names):
                out.append("'%s' is in area %d but its strand (%r) is not one of that area's strands, so it is missing from the area page" % (x["title"], n, x.get("strand")))
    learn = [x for x in ENTRIES if x["type"] == "learn"]
    for x in learn:
        if not x.get("audience"):
            out.append("Learn entry '%s' has no audience, so it disappears when the Made for menu is used" % x["title"])
        if x.get("length") and x["length"] not in LENGTHS:
            out.append("Learn entry '%s' has a length (%r) that is not one of the Length menu's bands" % (x["title"], x["length"]))
    unstated = [x["title"] for x in learn if not x.get("length")]
    if unstated:
        out.append("%d Learn entries have no running time, so the Length menu files them under '%s': %s" % (len(unstated), NO_LENGTH, "; ".join(unstated)))
    for p in WATCH_START:
        if not any(x["type"] == "watch" and x["title"].lower().startswith(p.lower()) for x in ENTRIES):
            out.append("Watch 'Start with these three' pick '%s' matches no Watch title, so it is left out" % p)
    for x in ENTRIES:
        if any(str(m).strip().lower() in ("none", "") for m in x["meta"]):
            out.append("empty or 'None' detail left out of the card for '%s': %r" % (x["title"], x["meta"]))
    return out


if __name__ == "__main__":
    build_home()
    build_types()
    build_areas()
    build_domains()
    build_stubs()
    build_vtlm()
    build_home_block()
    build_search_index()
    build_sitemap()
    build_404()
    print("Built %d library pages from %d entries." % (len(BUILT), len(ENTRIES)))
    print("Colon rule: capital added after a colon in %d texts." % len(CAP_CHANGED))
    for w in warnings():
        print("WARNING: " + w)
