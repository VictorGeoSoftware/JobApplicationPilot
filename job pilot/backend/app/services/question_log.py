from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class QuestionLogger:
    def __init__(self, file_path: Path, max_logs: int) -> None:
        self.file_path = file_path
        self.max_logs = max_logs
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]\n", encoding="utf-8")

    def save(self, question: str) -> None:
        try:
            rows = json.loads(self.file_path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                rows = []
        except json.JSONDecodeError:
            rows = []

        rows.append({
            "question": question,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        if len(rows) > self.max_logs:
            rows = rows[-self.max_logs :]

        self.file_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
