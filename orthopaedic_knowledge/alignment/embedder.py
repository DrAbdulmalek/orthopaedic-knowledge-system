"""تضمينات دلالية محلية عبر ONNX Runtime — ملفات النموذج تُوفر محلياً فقط.

لا تنزيل، لا استدعاء شبكة، لا HuggingFace hub. إن لم يوجد النموذج على القرص
فالوضع يبقى معجمياً (fallback) — الفشل آمن وليس تخميناً.

النماذج المدعومة بمجلدات ONNX محلية:
* BGE-M3 (onnx) — دقة أعلى
* paraphrase-multilingual-MiniLM-L12-v2 (onnx) — خفيف
"""

from __future__ import annotations

from pathlib import Path


class OnnxEmbedder:
    """غلاف ONNX Runtime لنموذج تضمين محلي متعدد اللغات."""

    def __init__(self, model_dir: str | Path) -> None:
        d = Path(model_dir)
        model_file = d / "model.onnx"
        if not model_file.exists():
            raise FileNotFoundError(
                f"لا يوجد نموذج ONNX محلي في {d} — وضع Local-First يمنع التنزيل؛ "
                "ضع ملف model.onnx + tokenizer.json في المجلد أو استخدم الوضع المعجمي."
            )
        import numpy as np
        from tokenizers import Tokenizer

        import onnxruntime as ort

        self._np = np
        self.session = ort.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.input_names = {i.name for i in self.session.get_inputs()}

    def _encode(self, texts: list[str]):
        np = self._np
        enc = self.tokenizer.encode_batch(texts)
        max_len = max(len(e.ids) for e in enc) or 1
        input_ids = np.zeros((len(enc), max_len), dtype=np.int64)
        attention = np.zeros((len(enc), max_len), dtype=np.int64)
        for r, e in enumerate(enc):
            input_ids[r, : len(e.ids)] = e.ids
            attention[r, : len(e.ids)] = e.attention_mask
        feed = {"input_ids": input_ids, "attention_mask": attention}
        feed = {k: v for k, v in feed.items() if k in self.input_names}
        out = self.session.run(None, feed)[0]
        mask = attention[:, :, None].astype(np.float32)
        emb = (out * mask).sum(1) / np.clip(mask.sum(1), 1e-9, None)
        emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)
        return emb

    def similarity(self, a: str, b: str) -> float:
        va, vb = self._encode([a, b])
        return float((va * vb).sum())


def build_embedder(model_dir: str | None) -> OnnxEmbedder | None:
    """أعد المغلف إن توفر نموذج محلي؛ وإلا None (وضع معجمي)."""
    if not model_dir:
        return None
    try:
        return OnnxEmbedder(model_dir)
    except Exception:
        return None
