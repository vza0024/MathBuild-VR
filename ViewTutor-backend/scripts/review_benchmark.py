"""Side-by-side review of tutor replies across benchmark settings.

For every request (same question, learner state and support type), shows each
setting's reply next to the others, with its latency and automatic flags:

  blocked       answer protection replaced the reply with a fallback
  exact_move    the reply tells the learner exactly how many objects to move
  long          more than 45 words (the prompt's limit)
  failed        the API call failed
  slow          over 6 seconds

Writes review.html (open in a browser) and review.csv (open in Excel/Sheets; the
"best" column is for your own choice per row) into the benchmark folder, and
prints a per-setting summary.

    python scripts/review_benchmark.py samples/benchmark/<time>
"""
from __future__ import annotations

import csv
import html
import json
import statistics
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from app.fallback import states_exact_move  # noqa: E402

SLOW_MS = 6000
MAX_WORDS = 45


def flags(log: dict) -> list[str]:
    out = []
    if log["status"] == "fallback_blocked":
        out.append("blocked")
    if log["status"] == "fallback_llm_error":
        out.append("failed")
    text = log.get("final_text") or ""
    if log["status"] != "confirmed_correct" and states_exact_move(text):
        out.append("exact_move")
    if len(text.split()) > MAX_WORDS:
        out.append("long")
    if (log.get("api_latency_ms") or 0) > SLOW_MS:
        out.append("slow")
    return out


def load(folder: Path) -> dict[str, list[dict]]:
    runs = {}
    for samples in sorted(folder.glob("*/tutor/samples.jsonl")):
        name = samples.parent.parent.name
        runs[name] = [json.loads(line) for line in samples.read_text(encoding="utf-8").splitlines() if line.strip()]
    return runs


def key(sample: dict) -> tuple:
    r = sample["request"]
    return (sample["question_id"], sample["state_label"], r["support_type"])


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    runs = load(folder)
    if not runs:
        sys.exit(f"No */tutor/samples.jsonl under {folder}")
    names = list(runs)
    by_key = {name: {key(s): s for s in samples} for name, samples in runs.items()}
    keys = list(by_key[names[0]])

    rows = []
    for k in keys:
        base = by_key[names[0]][k]
        if base["log"]["status"] == "confirmed_correct":
            continue  # fixed confirmation, no LLM call: identical for every setting
        row = {"question": base["question_id"], "interaction": base["interaction"], "state": base["state_label"],
               "support_type": base["request"]["support_type"], "story": base["story"],
               "learner_state": json.dumps({a: b for a, b in base["request"]["learner_state"].items()
                                            if a not in ("answer", "state_note")})}
        for name in names:
            sample = by_key[name].get(k)
            if sample is None:
                row[name], row[f"{name} ms"], row[f"{name} flags"] = "(missing)", "", ""
                continue
            log = sample["log"]
            row[name] = log.get("final_text") or ""
            row[f"{name} ms"] = round(log.get("api_latency_ms") or 0)
            row[f"{name} flags"] = ", ".join(flags(log))
        row["best"] = ""
        rows.append(row)

    with (folder / "review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    cells = []
    for row in rows:
        replies = "".join(
            f"<td><div>{html.escape(str(row[n]))}</div><small>{row[f'{n} ms']} ms"
            f"{' · <b>' + html.escape(row[f'{n} flags']) + '</b>' if row[f'{n} flags'] else ''}</small></td>"
            for n in names)
        cells.append(f"<tr><td><b>{row['interaction']}</b><br>{html.escape(row['state'])}<br>"
                     f"<i>{row['support_type']}</i><br><small>{html.escape(row['learner_state'])}</small></td>"
                     f"{replies}</tr>")
    head = "".join(f"<th>{html.escape(n)}</th>" for n in names)
    page = f"""<!doctype html><meta charset="utf-8"><title>Tutor replies by setting</title>
<style>body{{font:14px system-ui;margin:16px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;
padding:6px;vertical-align:top;max-width:340px}}th{{position:sticky;top:0;background:#eee}}small{{color:#666}}
b{{color:#b00}}</style><h1>Tutor replies by setting</h1>
<table><tr><th>Situation</th>{head}</tr>{''.join(cells)}</table>"""
    (folder / "review.html").write_text(page, encoding="utf-8")

    print(f"{'setting':28} {'mean ms':>8} {'p95 ms':>8} {'blocked':>8} {'exact':>6} {'long':>5} {'failed':>7}")
    for name in names:
        logs = [s["log"] for s in runs[name] if s["log"]["status"] != "confirmed_correct"]
        ms = sorted(l.get("api_latency_ms") or 0 for l in logs)
        f = [flags(l) for l in logs]
        p95 = ms[max(0, int(round(0.95 * len(ms))) - 1)] if ms else 0
        print(f"{name:28} {statistics.mean(ms):8.0f} {p95:8.0f} {sum('blocked' in x for x in f):8} "
              f"{sum('exact_move' in x for x in f):6} {sum('long' in x for x in f):5} {sum('failed' in x for x in f):7}")
    print(f"\nreview: {folder / 'review.html'}   spreadsheet: {folder / 'review.csv'}")


if __name__ == "__main__":
    main()
