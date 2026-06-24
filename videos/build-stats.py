#!/usr/bin/env python3
"""Generate videos/stats.json (per-episode performance) from the rtd-social D1.

stats.json shape: { "Ep N": {views, likes, comments, watch_time_minutes,
  avg_view_duration_seconds, avg_view_percentage, impressions, ctr,
  subscribers_gained, as_of, source, youtube_id} }
Only the latest snapshot per video is emitted; nulls are kept so the renderer can show
just the metrics that exist. A missing episode entry => the card shows no stats.

REPRODUCE (orchestrator-side; the D1 is read via the Cloudflare MCP, no secret handling):
  1) Cloudflare MCP d1_query on database d298499d-abb8-4009-b184-9bd8145617c1:
       SELECT v.episode, s.youtube_id, s.as_of, s.source, s.views, s.likes, s.comments,
              s.watch_time_minutes, s.avg_view_duration_seconds, s.avg_view_percentage,
              s.impressions, s.ctr, s.subscribers_gained
       FROM stats s
       JOIN videos v ON v.id = s.video_id
       WHERE v.series = 'claude-code'
         AND s.as_of = (SELECT MAX(as_of) FROM stats s2 WHERE s2.video_id = s.video_id)
       ORDER BY CAST(v.episode AS INTEGER);
  2) Save the MCP result JSON to a file, then:
       python3 videos/build-stats.py <export.json> > videos/stats.json
The export may be the raw MCP response ({"result":[{"results":[...]}]}) or a flat [rows].
"""
import json
import sys

METRICS = (
    "views", "likes", "comments", "watch_time_minutes", "avg_view_duration_seconds",
    "avg_view_percentage", "impressions", "ctr", "subscribers_gained",
)


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
        if not ep:
            continue
        entry = {m: row.get(m) for m in METRICS}
        entry["as_of"] = row.get("as_of")
        entry["source"] = row.get("source")
        entry["youtube_id"] = row.get("youtube_id")
        out[ep] = entry
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    data = json.load(sys.stdin if src == "-" else open(src, encoding="utf-8"))
    json.dump(build(rows_from(data)), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
