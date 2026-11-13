# The Knowledge Nest Library

The library pages on the site are generated. Nobody edits `library*.html` by hand.

## How an update flows

1. **The catalogue sheet is the source.** Entries are added or corrected there.
2. **`library/data/library.json`** is the cleaned, publishable copy of the catalogue. It holds only
   entries whose link loaded and whose status is not "Needs checking" or "To source".
   It is produced by `library/tools/prepare.py` from an export of the sheet.
3. **`python3 library/build.py`** turns `library.json` into the library pages, the home page's
   library sections, the search index and the sitemap. The header, menu and footer are copied from
   `about.html`, so a menu change there flows to every library page on the next build.
4. **GitHub does the rebuild automatically.** Whenever a change under `library/` reaches the `main`
   branch, the "Library upkeep" workflow runs the build and commits the refreshed pages.
5. **Links are checked every week.** The same workflow runs `library/tools/check_links.py` each
   Monday morning and opens an issue listing any link that has died.

## Files

| File | What it is |
|---|---|
| `library/build.py` | The page generator. Also holds the "Start here" topics, the must-listen shows and the categories. |
| `library/data/library.json` | Published entries, areas, shows and the Victorian view. |
| `library/data/summaries.json` | Short video summaries, keyed by link. |
| `library/data/shows.json` | Podcast show links, cover art addresses and descriptions. |
| `library/tools/prepare.py` | Sheet export to `library.json`. |
| `library/tools/check_links.py` | Link checker. |
| `library/search.js`, `library/filter.js` | Search on the library home, filters on Watch and Listen. |

## Ground rules

- Link out; never copy or host other people's work.
- Every entry names its creator or source.
- The catalogue sheet's working notes stay out of this public repository.
