"""Media retrieval for Ask Anton.

Instead of stuffing the entire media catalog into the prompt, we retrieve the few most
relevant items per question and show only those to the model. Matching is semantic
(a small local multilingual embedding model via fastembed - no external API, no DB), with
a keyword fallback so the service always works even if the model can't load.

The embedding model loads in a background thread at startup, so the app answers immediately
(keyword fallback) and upgrades to semantic once the model is ready.
"""

import re
import threading
import pathlib

_WORD = re.compile(r"[a-z0-9]+")
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_CACHE_DIR = str(pathlib.Path(__file__).parent / ".fastembed_cache")


def _doc(it: dict) -> str:
    tags = " ".join(it.get("tags") or [])
    desc = it.get("caption") or it.get("alt") or ""
    return f'{it.get("piece","")}. {desc}. {tags}'.strip()


class Retriever:
    def __init__(self, items: list):
        self.items = items or []
        self._docs = [_doc(it) for it in self.items]
        self._model = None
        self._emb = None      # normalized numpy matrix (n, d)
        self._np = None
        self._embed_lock = threading.Lock()
        self._status = "empty" if not self.items else "loading"
        if self.items:
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            import numpy as np
            from fastembed import TextEmbedding
            model = TextEmbedding(model_name=_MODEL_NAME, cache_dir=_CACHE_DIR)
            vecs = np.array(list(model.embed(self._docs)), dtype="float32")
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._np = np
            self._model = model
            self._emb = vecs / norms
            self._status = "semantic"
            print(f"[retrieval] semantic ready: {len(self.items)} items, dim={vecs.shape[1]}")
        except Exception as e:
            self._status = "keyword"
            print(f"[retrieval] embeddings unavailable, using keyword fallback: {e!r}")

    def status(self) -> str:
        return self._status

    def retrieve(self, query: str, k: int = 15) -> list:
        if not self.items:
            return []
        if self._emb is not None and self._model is not None:
            try:
                np = self._np
                with self._embed_lock:
                    qv = np.array(list(self._model.embed([query]))[0], dtype="float32")
                n = float(np.linalg.norm(qv)) or 1.0
                sims = self._emb @ (qv / n)
                order = np.argsort(-sims)[:k]
                return [self.items[i] for i in order]
            except Exception as e:
                print(f"[retrieval] query embed failed, keyword fallback: {e!r}")
        return self._keyword(query, k)

    def _keyword(self, query: str, k: int) -> list:
        q = set(_WORD.findall((query or "").lower()))
        if not q:
            return []
        scored = []
        for it, doc in zip(self.items, self._docs):
            score = len(q & set(_WORD.findall(doc.lower())))
            if score:
                scored.append((score, it))
        scored.sort(key=lambda x: -x[0])
        return [it for _, it in scored[:k]]
