from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ContextChunk:
    file_name: str
    text: str


class ContextStore:
    def __init__(self, docs_dir: Path) -> None:
        self.docs_dir = docs_dir
        self._chunks: list[ContextChunk] = []
        self._index_docs()

    def _index_docs(self) -> None:
        self._chunks = []
        if not self.docs_dir.exists():
            return

        for file_path in sorted(self.docs_dir.rglob("*")):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            text = ""
            if suffix in {".txt", ".md"}:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".json":
                text = self._read_json_text(file_path)
            elif suffix == ".pdf":
                text = self._read_pdf_text(file_path)

            clean = " ".join(text.split())
            if not clean:
                continue

            for chunk in self._chunk_text(clean):
                self._chunks.append(ContextChunk(file_name=file_path.name, text=chunk))

    def _read_json_text(self, file_path: Path) -> str:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
            return json.dumps(payload, ensure_ascii=True)
        except json.JSONDecodeError:
            return file_path.read_text(encoding="utf-8", errors="ignore")

    def _read_pdf_text(self, file_path: Path) -> str:
        try:
            reader = PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception:
            return ""

    def _chunk_text(self, text: str, chunk_size: int = 1100, overlap: int = 180) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = max(0, end - overlap)
        return chunks

    def retrieve(self, query: str, limit: int) -> list[ContextChunk]:
        if not self._chunks:
            return []

        query_tokens = self._tokenize(query)
        scored = []
        for chunk in self._chunks:
            score = self._score(query_tokens, self._tokenize(chunk.text))
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def _tokenize(self, text: str) -> set[str]:
        cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower())
        return {token for token in cleaned.split() if token}

    def _score(self, query_tokens: set[str], chunk_tokens: set[str]) -> float:
        if not query_tokens or not chunk_tokens:
            return 0.0
        common = len(query_tokens.intersection(chunk_tokens))
        return common / (len(query_tokens) ** 0.5)
