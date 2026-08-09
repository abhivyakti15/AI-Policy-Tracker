"""
Fetches news via NewsAPI ( https://newsapi.org), filter to things that look like state-level AI Policy
activity in India, deduplicate, normalize into the project's CSV schema, and write data/ai_policy_india_auto.csv

fetch -> filter/relevance -> dedupe -> categorize 
-> normalize (dates, state names) -> write CSV
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"

# Step 1 - Configuration - States we track, and how to build a search query for each. Extend this list to widen coverage.

STATES = {
    "Telangana":    {"code": "TG", "aliases": ["Telangana", "Hyderabad"]},
    "Karnataka":    {"code": "KA", "aliases": ["Karnataka", "Bengaluru", "Bangalore"]},
    "Tamil Nadu":    {"code": "TN", "aliases": ["Tamil Nadu", "Chennai"]},
    "Andhra Pradesh":    {"code": "AP", "aliases": ["Andhra Pradesh", "Amaravati", "Visakhapatnam", "Vizag"]},
    "Maharashtra":    {"code": "MH", "aliases": ["Maharashtra", "Mumbai", "Pune", "Nagpur"]},
    "Uttar Pradesh":    {"code": "UP", "aliases": ["Uttar Pradesh", "Lucknow"]},
    "Kerala":    {"code": "KL", "aliases": ["Kerala", "Kochi", "Thiruvananthapuram"]},
    "Goa":    {"code": "GA", "aliases": ["Goa"]}
}

AI_TERMS = ["artificial intelligence", "\"AI\" policy", "AI mission", "AI city"]
POLICY_TERMS = [
    "policy", "mission", "MoU", "memorandum of understanding", "task force",
    "centre of excellence", "center of excellence", "budget", "governance", 
    "advisory council", "regulation", "framework",
]

CATEGORY_KEYWORDS = {
    "Policy/Strategy": ["policy", "roadmap", "strategy", "mission", "framework"],
    "Institutional Setup": ["centre of excellence", "center of excellence", "task force", "advisory council", "ai city", "department", "university", "hub"],
    "Industy/Academia MoU": ["mou", "memorandum of understanding", "partnership", "signs deal", "tie-up", "tie up"],
    "Governance Deployment": ["deploy", "rollout", "roll out", "pilot", "healthcare", "agriculture", "policing", "police", "education", "e-governance", "citizen services"],
    "Budget & Funding": ["budget", "crore", "allocation", "fund", "investment of", "outlay"],
    "Regulatory/Ethics": ["ethic", "regulation", "regulatory", "responsible ai", "safe ai", "guidelines"],
    "Skilling/Workforce": ["skilling", "reskilling", "training", "workforce", "jobs", "internship"],
}

STATE_ALIASES_LOOKUP = {
    alias.lower(): canonical
    for canonical, info in STATES.items()
    for alias in info["aliases"] + [canonical]
}

# Step 2 - Fetching

def fetch_articles_for_state(state, api_key, days, page_size, session, cache_dir):
    import requests 

    query = f'({state}) AND ({" OR ".join(AI_TERMS)}) AND ({" OR ".join(POLICY_TERMS)})'
    from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    cache_key = re.sub(r"\W+", "_", state.lower())
    cache_path = os.path.join(cache_dir, f"{cache_key}_{from_date}.json")
    if os.path.exists(cache_path):
       with open(cache_path, encoding="utf-8") as f:
           return json.load(f).get("articles", [])

    params = {
       "q": query,
       "from": from_date,
       "language": "en",
       "sortBy": "relevancy",
       "pageSize": page_size,
       "apiKey": api_key,
    }
    resp = session.get(NEWSAPI_ENDPOINT, params=params, timeout=20)
    if resp.status_code == 429:
       print(f"  [{state}] rate limited by NewsAPI, backing off 5s and retrying once...", file=sys.stderr)
       time.sleep(5)
       resp = session.get(NEWSAPI_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()


    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
       json.dump(payload, f, ensure_ascii=False, indent=2)


    return payload.get("articles", [])

# Step 3 - Relevance

def looks_relevant(article, state):
    text = f"{article.get('title') or ''} {article.get('description') or ''}".lower()
    if state.lower() not in text and not any(a.lower() in text for a in STATES[state]["aliases"]):
       return False
    has_ai = "ai" in re.findall(r"\b\w+\b", text) or "artificial intelligence" in text
    has_policy_word = any(term.split()[0] in text for term in POLICY_TERMS)
    return has_ai and has_policy_word

# STep 4 - Deduplication

def title_similarity(a, b):
   return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def dedupe(articles, threshold=0.6):
   """Greedy clustering: each article joins the first existing cluster whose
   canonical title is similar enough, else starts a new cluster. Cheap and
   good enough at the volumes NewsAPI's free tier returns (dozens, not
   thousands, per query)."""
   clusters = []  # list of {canonical: article, members: [article, ...]}
   for art in sorted(articles, key=lambda a: a.get("publishedAt") or ""):
       title = art.get("title") or ""
       placed = False
       for cluster in clusters:
           if title_similarity(title, cluster["canonical"]["title"] or "") >= threshold:
               cluster["members"].append(art)
               placed = True
               break
       if not placed:
           clusters.append({"canonical": art, "members": [art]})
   return clusters

# Step 5 - Categorize (heuristic)

def categorize_heuristic(text):
   text = text.lower()
   scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in CATEGORY_KEYWORDS.items()}
   best = max(scores, key=scores.get)
   return best if scores[best] > 0 else "Governance Deployment"  # safest fallback bucket

# Step 6 - Normalize a cluster -> one CSV row

def normalize_cluster(cluster, state):
   canonical = cluster["canonical"]
   others = cluster["members"][1:]

   text_for_categorization = f"{canonical.get('title') or ''} {canonical.get('description') or ''}"
   headline = canonical.get("title") or ""
   summary = canonical.get("description") or ""
   category = categorize_heuristic(text_for_categorization)
   entities = ""


   published = canonical.get("publishedAt") or ""
   date = published[:10] if published else ""


   return {
       "state": state,
       "state_code": STATES[state]["code"],
       "date": date,
       "date_precision": "day" if date else "unknown",
       "headline": headline.strip(),
       "category": category,
       "summary": summary.strip(),
       "source_name": (canonical.get("source") or {}).get("name", ""),
       "source_url": canonical.get("url", ""),
       "entities": entities,
       "also_reported_by": "; ".join(
           (m.get("source") or {}).get("name", "") for m in others if (m.get("source") or {}).get("name")
       ),
       "notes": "auto-fetched via NewsAPI; heuristic categorization, unverified",
   }


# Step 7 -  Main

def main():
   parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
   parser.add_argument("--api-key", default="b09703ce22f64473b9791508a66765f2",
                    help="NewsAPI key")
   parser.add_argument("--days", type=int, default=90,
                        help="How many days back to search (free tier caps this at ~30)")
   parser.add_argument("--page-size", type=int, default=50, help="Max articles per state query (NewsAPI max 100)")
   parser.add_argument("--states", nargs="*", default=list(STATES.keys()),
                        help="Subset of states to fetch, e.g. --states Telangana Karnataka")
   parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "ai_policy_india_auto.csv"))
   parser.add_argument("--cache-dir", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
   args = parser.parse_args()

   if not args.api_key:
       parser.error("No NewsAPI key found. Pass --api-key or set NEWSAPI_KEY.")

   try:
       import requests
   except ImportError:
       parser.error("This script needs `requests`. Install with: pip install requests --break-system-packages")

   session = requests.Session()
   all_rows = []

   for state in args.states:
       if state not in STATES:
           print(f"  [skip] unknown state '{state}', not in STATES config", file=sys.stderr)
           continue
       print(f"Fetching: {state} ...")
       articles = fetch_articles_for_state(state, args.api_key, args.days, args.page_size, session, args.cache_dir)
       relevant = [a for a in articles if looks_relevant(a, state)]
       print(f"  {len(articles)} articles fetched, {len(relevant)} passed the relevance filter")

       clusters = dedupe(relevant)
       print(f"  {len(clusters)} clusters after dedup")

       for cluster in clusters:
           row = normalize_cluster(cluster, state)
           if row is not None:
               all_rows.append(row)

   all_rows.sort(key=lambda r: (r["state"], r["date"]))
   for i, row in enumerate(all_rows, start=1):
       row["id"] = f"AUTO-{i:03d}"

   fieldnames = ["id", "state", "state_code", "date", "date_precision", "headline", "category",
                 "summary", "source_name", "source_url", "entities", "also_reported_by", "notes"]

   os.makedirs(os.path.dirname(args.out), exist_ok=True)
   with open(args.out, "w", newline="", encoding="utf-8") as f:
       writer = csv.DictWriter(f, fieldnames=fieldnames)
       writer.writeheader()
       for row in all_rows:
           writer.writerow({k: row.get(k, "") for k in fieldnames})

   print(f"\nWrote {len(all_rows)} rows to {args.out}")
   print("NOTE: `summary` fields are the source's own description text, not paraphrased. "
       "Review before merging into the main dataset, and see the module docstring / "
       "RATIONALE.md for why that matters.")

if __name__ == "__main__":
   main()



