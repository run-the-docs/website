#!/usr/bin/env python3
"""Build videos/catalog.json + videos/captions.json for the data-driven /videos page.

catalog.json  = ordered editorial catalogue the page renders from. Per Claude Code
                episode: {ep, title, desc(html), poster, file, v916|null}. Plus an
                `extras` list for non-episode cards (the rig explainer).
captions.json = human prose only: {ep: {youtube, linkedin, x, tiktok}}.

This is the ONE-TIME bootstrap: it parses the legacy hardcoded videos.html cards +
the legacy videos/share-kit.json so the new data files reproduce today's page exactly
(a provable superset — same cards, identical captions). After the cutover, catalog.json
is human-owned editorial + (Phase 4) reconciler-owned media fields; captions.json is
hand-maintained. Re-run only to re-bootstrap from a legacy copy.

Usage: python3 videos/build-catalog.py [--check]
  --check : regenerate in-memory and fail if it differs from the committed files
            (drift guard for CI), instead of writing.
"""
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "videos.html")
SHARE_KIT = os.path.join(HERE, "share-kit.json")
CATALOG = os.path.join(HERE, "catalog.json")
CAPTIONS = os.path.join(HERE, "captions.json")

CLIP_RE = re.compile(r'<div class="clip">(.*?)</div>\s*</div>', re.S)
POSTER_RE = re.compile(r'poster="([^"]+)"')
SOURCE_RE = re.compile(r'<source\s+src="([^"]+)"')
EP_RE = re.compile(r'<span class="clip-ep">([^<]+)</span>')
TITLE_RE = re.compile(r'<div class="clip-title">(.*?)</div>', re.S)
DESC_RE = re.compile(r'<p class="clip-desc">(.*?)</p>', re.S)

VIDEO_CARD_RE = re.compile(r'<div class="video-card">(.*?)</div>\s*</div>\s*</section>', re.S)
BADGE_RE = re.compile(r'<span class="video-badge">(.*?)</span>', re.S)
VTITLE_RE = re.compile(r'<div class="video-title">(.*?)</div>', re.S)
VDESC_RE = re.compile(r'<p class="video-desc">(.*?)</p>', re.S)
LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
META_RE = re.compile(r'<p class="series-meta">(.*?)</p>', re.S)


def parse_episodes(html):
    eps = []
    for block in CLIP_RE.findall(html):
        ep = EP_RE.search(block)
        title = TITLE_RE.search(block)
        desc = DESC_RE.search(block)
        poster = POSTER_RE.search(block)
        src = SOURCE_RE.search(block)
        if not (ep and title and desc and poster and src):
            continue
        eps.append({
            "ep": ep.group(1).strip(),
            "title": title.group(1).strip(),
            "desc": desc.group(1).strip(),
            "poster": poster.group(1).strip(),
            "file": src.group(1).strip(),
        })
    return eps


def parse_extras(html):
    extras = []
    m = VIDEO_CARD_RE.search(html)
    if not m:
        return extras
    block = m.group(1)
    badge = BADGE_RE.search(block)
    title = VTITLE_RE.search(block)
    desc = VDESC_RE.search(block)
    poster = POSTER_RE.search(block)
    src = SOURCE_RE.search(block)
    links = [{"href": h, "label": re.sub(r"\s+", " ", lab).strip()}
             for h, lab in LINK_RE.findall(block)]
    extras.append({
        "badge": badge.group(1).strip() if badge else "",
        "title": title.group(1).strip() if title else "",
        "desc": desc.group(1).strip() if desc else "",
        "poster": poster.group(1).strip() if poster else "",
        "file": src.group(1).strip() if src else "",
        "links": links,
    })
    return extras


def build():
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    with open(SHARE_KIT, encoding="utf-8") as f:
        kit = json.load(f)

    episodes = parse_episodes(html)
    extras = parse_extras(html)
    metas = META_RE.findall(html)
    cc_meta = re.sub(r"\s+", " ", metas[0]).strip() if metas else ""

    captions = {}
    for e in episodes:
        ep = e["ep"]
        entry = kit.get(ep, {})
        e["v916"] = entry.get("v916")  # null if not yet on R2
        caps = entry.get("captions")
        if caps:
            captions[ep] = caps

    catalog = {
        "_generated_by": "videos/build-catalog.py (bootstrap from legacy videos.html + share-kit.json)",
        "claude_code": {"title": "claude code", "meta": cc_meta, "episodes": episodes},
        "extras": extras,
    }

    # ---- integrity asserts: provable no-loss migration ----
    kit_eps = [k for k, v in kit.items() if v.get("captions")]
    cat_eps = [e["ep"] for e in episodes]
    missing = [k for k in kit_eps if k not in cat_eps]
    assert not missing, f"share-kit episodes with no card: {missing}"
    for ep, caps in captions.items():
        assert caps == kit[ep]["captions"], f"caption drift for {ep}"
    for e in episodes:
        assert e["v916"] == kit.get(e["ep"], {}).get("v916"), f"v916 drift for {e['ep']}"
        assert e["title"] and e["desc"] and e["poster"] and e["file"], f"incomplete card {e['ep']}"
    assert len(episodes) == len(kit_eps), f"card count {len(episodes)} != share-kit {len(kit_eps)}"
    assert extras and extras[0]["file"], "rig extra card not extracted"

    return catalog, captions, len(episodes), len(extras)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def main():
    catalog, captions, n_ep, n_extra = build()
    check = "--check" in sys.argv
    if check:
        cur_cat = open(CATALOG, encoding="utf-8").read() if os.path.exists(CATALOG) else ""
        cur_cap = open(CAPTIONS, encoding="utf-8").read() if os.path.exists(CAPTIONS) else ""
        drift = (cur_cat != dump(catalog)) or (cur_cap != dump(captions))
        print("DRIFT" if drift else "OK", f"({n_ep} episodes, {n_extra} extra)")
        sys.exit(1 if drift else 0)
    with open(CATALOG, "w", encoding="utf-8") as f:
        f.write(dump(catalog))
    with open(CAPTIONS, "w", encoding="utf-8") as f:
        f.write(dump(captions))
    print(f"wrote catalog.json ({n_ep} episodes, {n_extra} extra) + captions.json ({len(captions)} episodes)")


if __name__ == "__main__":
    main()
