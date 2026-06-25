// Live iCalendar feed for the Run the Docs Claude Code video schedule.
//
//   Route : GET /schedule.ics   (Cloudflare Pages Function)
//   Data  : the same-origin, committed videos/posted.json (regenerated from the
//           rtd-social D1 on every schedule change), fetched per request.
//   Output: RFC 5545 VCALENDAR — always reflects the current posted.json.
//
// No D1 binding and no extra deploy permissions: it just reads a static asset,
// so it ships with the normal Pages deploy. Read-only; emits no secret.

const PRODID = "-//Run the Docs//schedule//EN";
const ENC = new TextEncoder();

const esc = (s) =>
  String(s == null ? "" : s)
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");

function fold(line) {
  if (ENC.encode(line).length <= 75) return line;
  const parts = [];
  let cur = "";
  for (const ch of Array.from(line)) {
    if (ENC.encode(cur + ch).length > 73) {
      parts.push(cur);
      cur = "";
    }
    cur += ch;
  }
  parts.push(cur);
  return parts.join("\r\n ");
}

const stamp = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

function parseInstant(s) {
  if (typeof s !== "string") return null;
  let v = s.trim();
  if (!v) return null;
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(v)) v = v.replace(" ", "T");
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(v)) v += "Z";
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
}

function youtubeId(url) {
  if (typeof url !== "string") return null;
  const m = url.match(/[?&]v=([^&#]+)/) || url.match(/youtu\.be\/([^?&#/]+)/);
  return m ? m[1] : null;
}

function buildIcs(data) {
  const rows = [];
  for (const [episode, platforms] of Object.entries(data || {})) {
    const yt = platforms && platforms.youtube;
    if (!yt) continue;
    if (yt.status !== "posted" && yt.status !== "scheduled") continue;
    const start = parseInstant(yt.publish_at);
    if (!start) continue;
    rows.push({ episode, status: yt.status, start, yid: youtubeId(yt.url) });
  }
  rows.sort((a, b) => a.start - b.start);

  const dtstamp = stamp(new Date());
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:" + PRODID,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Run the Docs — video schedule",
    "X-WR-TIMEZONE:UTC",
    "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    "X-PUBLISHED-TTL:PT1H",
    "X-WR-CALDESC:Live Claude Code video drip (from videos/posted.json)",
  ];

  for (const row of rows) {
    const end = new Date(row.start.getTime() + 15 * 60000);
    const posted = row.status === "posted";
    const uid = "rtd-" + String(row.yid || "ep-" + row.episode).replace(/[^\w-]/g, "") + "@run-the-docs";
    lines.push(
      "BEGIN:VEVENT",
      "UID:" + uid,
      "DTSTAMP:" + dtstamp,
      "DTSTART:" + stamp(row.start),
      "DTEND:" + stamp(end),
      "SUMMARY:📺 RtD " + esc(row.episode) + (posted ? " ✓ live" : " → live"),
      "DESCRIPTION:" +
        esc(
          "Run the Docs Claude Code Short" +
            (posted ? " (published)" : " (scheduled)") +
            (row.yid ? ". https://youtu.be/" + row.yid : "")
        ),
      "TRANSP:TRANSPARENT"
    );
    if (row.yid) lines.push("URL:https://youtu.be/" + esc(row.yid));
    lines.push("END:VEVENT");
  }

  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}

export async function onRequestGet({ request }) {
  let data;
  try {
    const origin = new URL(request.url).origin;
    const r = await fetch(origin + "/videos/posted.json", { headers: { accept: "application/json" } });
    if (!r.ok) throw new Error("posted.json HTTP " + r.status);
    data = await r.json();
  } catch (err) {
    console.error("schedule.ics source error:", err && err.message);
    return new Response("Schedule temporarily unavailable.", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
    });
  }
  return new Response(buildIcs(data), {
    headers: {
      "content-type": "text/calendar; charset=utf-8",
      "content-disposition": 'inline; filename="rtd-schedule.ics"',
      "cache-control": "public, max-age=900",
    },
  });
}
