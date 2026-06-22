#!/usr/bin/env python3
"""Generate videos/posted.json (per-episode, per-platform posting status) from the
rtd-social D1.

posted.json shape: { "Ep N": { "<platform>": {"status","url","posted_at"} } }
Only non-'none' entries are recorded; the renderer treats a missing entry as not-posted.
The Share kit shows these 4 platforms: youtube, tiktok, linkedin, x (the D1 also tracks
instagram, which the site doesn't surface).

REPRODUCE (orchestrator-side; the D1 is read via the Cloudflare MCP, no secret handling):
  1) Cloudflare MCP d1_query on database d298499d-abb8-4009-b184-9bd8145617c1:
       SELECT v.episode, p.platform, p.status, p.url, p.posted_at
       FROM videos v JOIN postings p ON p.video_id = v.id
       WHERE v.series = 'claude-code'
         AND p.platform IN ('youtube','tiktok','linkedin','x')
         AND p.status != 'none'
       ORDER BY CAST(v.episode AS INTEGER), p.platform;
  2) Save the MCP result JSON to a file, then:
       python3 videos/build-posted.py <export.json> > videos/posted.json
The export may be the raw MCP response ({"result":[{"results":[...]}]}) or a flat [rows].
"""
import json, sys

SITE_PLATFORMS = {"youtube", "tiktok", "linkedin", "x"}


def rows_from(data):
    """Accept the raw Cloudflare MCP d1_query response or a flat list of row dicts."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        r = data.get("result", data)
        if isinstance(r, list) and r and isinstance(r[0], dict) and "results" in r[0]:
            return r[0]["results"]
        if isinstance(r, dict) and "results" in r:
            return r["results"]
        if isinstance(r, list):
            return r
    return []


def build(rows):
    out = {}
    for row in rows:
        ep = row.get("episode")
        plat = row.get("platform")
        if not ep or plat not in SITE_PLATFORMS:
            continue
        if row.get("status") in (None, "none"):
            continue
        out.setdefault(ep, {})[plat] = {
            "status": row["status"],
            "url": row.get("url"),
            "posted_at": row.get("posted_at"),
        }
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    data = json.load(sys.stdin if src == "-" else open(src, encoding="utf-8"))
    posted = build(rows_from(data))
    json.dump(posted, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
