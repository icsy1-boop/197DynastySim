"""
agents/memory.py
Generative Agents memory stream — Park et al. 2023.
Replaces the simple 20-entry rolling buffer for political/key agents.

Retrieval score = recency × importance × relevance (all normalized to [0,1])
  recency   = 0.995^(current_tick - last_accessed)
  importance = stored score / 10
  relevance  = TF-IDF cosine similarity against query

Reflection is triggered when the sum of un-reflected importance scores > 150.
"""

import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ── Memory object ─────────────────────────────────────────────────────────────

@dataclass
class MemoryObject:
    memory_id:    str
    description:  str
    timestamp:    int           # sim tick when created
    last_accessed: int          # sim tick of last retrieval (updated on access)
    importance:   float         # 1–10, scored by Qwen or heuristic
    memory_type:  str           # "observation" | "reflection" | "plan"
    emotional_tag: str          # "neutral" | "satisfied" | "frustrated" | "fearful" | "angry"
    _term_freq:   dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "memory_id":    self.memory_id,
            "description":  self.description,
            "timestamp":    self.timestamp,
            "last_accessed": self.last_accessed,
            "importance":   round(self.importance, 2),
            "memory_type":  self.memory_type,
            "emotional_tag": self.emotional_tag,
        }


# ── Memory stream ─────────────────────────────────────────────────────────────

class MemoryStream:
    """
    Full Generative Agents memory stream for a single political agent.
    Citizen agents keep the old MemoryEntry rolling buffer instead.
    """

    RECENCY_DECAY = 0.995           # exponential decay per tick
    REFLECTION_THRESHOLD = 150.0    # importance sum before reflecting
    MAX_STREAM_SIZE = 500           # hard cap

    _STOPWORDS = frozenset({
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "and", "or", "but", "not",
        "i", "you", "he", "she", "it", "we", "they", "my", "your",
    })

    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self._memories: list[MemoryObject] = []
        self._idf: dict[str, float] = {}
        self._idf_dirty: bool = True
        self._unreflected_importance: float = 0.0

    # ── Adding memories ───────────────────────────────────────────────────────

    def add(
        self,
        description: str,
        tick: int,
        importance: float,
        memory_type: str = "observation",
        emotional_tag: str = "neutral",
    ) -> MemoryObject:
        m = MemoryObject(
            memory_id=uuid.uuid4().hex,
            description=description,
            timestamp=tick,
            last_accessed=tick,
            importance=max(1.0, min(10.0, importance)),
            memory_type=memory_type,
            emotional_tag=emotional_tag,
        )
        m._term_freq = self._compute_tf(description)
        self._memories.append(m)
        self._idf_dirty = True

        if memory_type != "reflection":
            self._unreflected_importance += importance

        # Trim oldest when over limit
        if len(self._memories) > self.MAX_STREAM_SIZE:
            self._memories.pop(0)

        return m

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self, query: str, current_tick: int, top_k: int = 10
    ) -> list[MemoryObject]:
        """
        Score all memories by recency × importance × relevance, return top-k.
        Updates last_accessed on returned memories.
        """
        if not self._memories:
            return []

        if self._idf_dirty:
            self._rebuild_idf()

        query_tf = self._compute_tf(query)

        raw_recency    = []
        raw_importance = []
        raw_relevance  = []

        for m in self._memories:
            age = current_tick - m.last_accessed
            raw_recency.append(self.RECENCY_DECAY ** age)
            raw_importance.append(m.importance / 10.0)
            raw_relevance.append(self._cosine_similarity(query_tf, m._term_freq))

        # Normalize each dimension to [0, 1]
        def _norm(vals):
            lo, hi = min(vals), max(vals)
            if hi == lo:
                return [1.0] * len(vals)
            return [(v - lo) / (hi - lo) for v in vals]

        recency_n    = _norm(raw_recency)
        importance_n = _norm(raw_importance)
        relevance_n  = _norm(raw_relevance)

        scored = []
        for i, m in enumerate(self._memories):
            score = recency_n[i] * importance_n[i] * relevance_n[i]
            scored.append((score, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        result = []
        for _, i in top:
            self._memories[i].last_accessed = current_tick
            result.append(self._memories[i])
        return result

    # ── Reflection trigger ────────────────────────────────────────────────────

    def should_reflect(self) -> bool:
        return self._unreflected_importance >= self.REFLECTION_THRESHOLD

    def mark_reflected(self):
        self._unreflected_importance = 0.0

    # ── Convenience ───────────────────────────────────────────────────────────

    def get_recent_plan(self) -> Optional[MemoryObject]:
        plans = [m for m in reversed(self._memories) if m.memory_type == "plan"]
        return plans[0] if plans else None

    def recent_as_str(self, current_tick: int, top_k: int = 5) -> str:
        """Return retrieved memories as a prompt-friendly string."""
        memories = self.retrieve("recent events goals actions", current_tick, top_k)
        if not memories:
            return "no notable events"
        lines = [
            f"[{m.memory_type.upper()} imp={m.importance:.0f}] {m.description}"
            for m in memories
        ]
        return "; ".join(lines)

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> list[dict]:
        """Top 20 by last_accessed descending — cap for JSON file size."""
        sorted_mems = sorted(
            self._memories, key=lambda m: m.last_accessed, reverse=True
        )
        return [m.to_dict() for m in sorted_mems[:20]]

    # ── TF-IDF internals ──────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z]+", text.lower())
        return [t for t in tokens if t not in self._STOPWORDS and len(t) > 1]

    def _compute_tf(self, text: str) -> dict[str, float]:
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        total = len(tokens)
        return {t: c / total for t, c in counts.items()}

    def _rebuild_idf(self):
        n = len(self._memories)
        if n == 0:
            self._idf = {}
            self._idf_dirty = False
            return
        df: dict[str, int] = {}
        for m in self._memories:
            for term in m._term_freq:
                df[term] = df.get(term, 0) + 1
        self._idf = {
            term: math.log(n / (1 + count))
            for term, count in df.items()
        }
        self._idf_dirty = False

    def _tfidf_vec(self, tf: dict[str, float]) -> dict[str, float]:
        return {t: tf[t] * self._idf.get(t, 0.0) for t in tf}

    def _cosine_similarity(self, tf_a: dict, tf_b: dict) -> float:
        if not tf_a or not tf_b:
            return 0.0
        vec_a = self._tfidf_vec(tf_a)
        vec_b = self._tfidf_vec(tf_b)
        shared = set(vec_a) & set(vec_b)
        if not shared:
            return 0.0
        dot = sum(vec_a[t] * vec_b[t] for t in shared)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ── Importance heuristic (fallback when Qwen offline) ─────────────────────────

_HIGH_IMPORTANCE_KEYWORDS = frozenset({
    "corrupt", "bribe", "embezzle", "scandal", "ghost", "kickback",
    "extort", "steal", "fraud", "cover", "suppress",
})
_MEDIUM_KEYWORDS = frozenset({
    "election", "vote", "contract", "arrest", "protest", "publish",
    "investigate", "audit", "flag", "report", "resign",
})


def heuristic_importance(description: str) -> float:
    low = description.lower()
    for kw in _HIGH_IMPORTANCE_KEYWORDS:
        if kw in low:
            return 8.0
    for kw in _MEDIUM_KEYWORDS:
        if kw in low:
            return 6.0
    return 3.0
