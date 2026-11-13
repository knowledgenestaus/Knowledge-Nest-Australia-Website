"""Collect preview images for video entries: YouTube stills by id, and each other page's own og:image.
Writes library/data/thumbs.json (url -> image url). Images are linked, never copied."""
import json, os, re, sys, urllib.request, concurrent.futures as cf
from urllib.parse import urlparse, parse_qs, urljoin
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(ROOT, "library", "data")
entries = json.load(open(os.path.join(D, "library.json"), encoding="utf8"))["entries"]
learn = json.load(open(os.path.join(D, "learn.json"), encoding="utf8"))["entries"]
urls = sorted(set(x["url"] for x in entries if x["type"] == "watch") | set(x["url"] for x in learn))
out_path = os.path.join(D, "thumbs.json")
out = json.load(open(out_path)) if os.path.exists(out_path) else {}

def yt(u):
    p = urlparse(u)
    if "youtu.be" in p.netloc: return p.path.strip("/")
    if "youtube.com" in p.netloc: return (parse_qs(p.query).get("v") or [None])[0]

def og(u):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (compatible; KnowledgeNestLibrary/1.0)"})
        html = urllib.request.urlopen(req, timeout=12).read(300000).decode("utf8", "ignore")
        m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', html) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image', html)
        return u, urljoin(u, m.group(1).replace("&amp;", "&")) if m else None
    except Exception as ex:
        return u, None

todo = []
for u in urls:
    v = yt(u)
    if v: out[u] = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % v
    elif u not in out: todo.append(u)
with cf.ThreadPoolExecutor(12) as ex:
    for u, img in ex.map(og, todo):
        if img and img.startswith("https://"): out[u] = img
json.dump(out, open(out_path, "w"), indent=1, sort_keys=True)
print(len(urls), "videos,", len(out), "with an image")
