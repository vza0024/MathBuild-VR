"""Research log: event lines as things happen, one final record per request.

File: `<LOG_DIR>/YYYY-MM-DD.jsonl` (UTC date). Each line is JSON with a `type`:

- ``event``  written immediately when it happens (e.g. the raw LLM output or a
  failure), so a later crash cannot lose it.
- ``final``  written exactly once per `/api/tutor` request, by the logging
  middleware only. Every other component adds fields to the request's
  `RequestRecord`; none of them writes a final line.

Both carry the same `request_id`. Logging never raises: a write error is
reported on stderr and the request still gets its response. Because of that,
"exactly one final record" holds only while storage is healthy, so failures are
made visible: `WRITE_FAILURES` counts them, `/api/health` reports them and
a storage check, and each /api/tutor response carries `X-Research-Log: ok|failed`.
Experiment scripts stop if storage is not healthy.

Privacy: the log holds the learner state, the learner's typed message and the
tutor conversation, which the analysis needs. It holds no names, accounts or
device identifiers, and never the API key. Store logs on restricted storage.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

# Logging health, process-wide. Read by /api/health and the sample script.
WRITE_FAILURES = 0
LAST_WRITE_ERROR: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RequestRecord:
    """Everything known about one request. Filled in by the pipeline."""

    def __init__(self, log_dir: Path, request_id: str | None = None):
        self.log_dir = log_dir
        self.request_id = request_id or str(uuid.uuid4())
        self.started = time.perf_counter()
        self.fields: dict[str, Any] = {"request_id": self.request_id, "timestamp": _now_iso()}
        self._finalized = False

    def add(self, **fields: Any) -> None:
        self.fields.update(fields)

    def event(self, kind: str, **data: Any) -> None:
        """Write an event line now."""
        _write(self.log_dir, {"type": "event", "request_id": self.request_id,
                              "timestamp": _now_iso(), "event": kind, **data})

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000

    def finalize(self) -> bool:
        """Write the final record. Only the middleware calls this.

        Returns True if the final record was written now; False if it was
        already written before or the write failed.
        """
        if self._finalized:
            return False
        self._finalized = True
        self.fields.setdefault("total_latency_ms", round(self.elapsed_ms(), 1))
        return _write(self.log_dir, {"type": "final", **self.fields})


def _write(log_dir: Path, line: dict[str, Any]) -> bool:
    global WRITE_FAILURES, LAST_WRITE_ERROR
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        text = json.dumps(line, ensure_ascii=False, default=str)
        with _LOCK, path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
        return True
    except Exception as exc:  # logging must never break a response
        with _LOCK:
            WRITE_FAILURES += 1
            LAST_WRITE_ERROR = f"{type(exc).__name__}: {exc}"[:300]
        print(f"research log write failed: {LAST_WRITE_ERROR}", file=sys.stderr)
        return False


def storage_check(log_dir: Path) -> tuple[bool, str | None]:
    """Can the log directory be created and appended to? Writes and removes a probe file."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        probe = log_dir / f".probe-{uuid.uuid4().hex}"
        with probe.open("a", encoding="utf-8") as handle:
            handle.write("ok\n")
        probe.unlink()
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:300]


def read_log(log_dir: Path) -> list[dict[str, Any]]:
    """All lines from all log files (tests and analysis)."""
    lines: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("*.jsonl")):
        lines.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return lines
