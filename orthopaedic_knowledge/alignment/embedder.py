"""تضمينات دلالية محلية عبر ONNX Runtime — ملفات النموذج تُوفر محلياً فقط.

لا تنزيل، لا استدعاء شبكة، لا HuggingFace hub.

قواعد صارمة:
* ``build_embedder(None)`` → وضع معجمي (بلا نموذج — قرار تصميمي، ليس فشلاً).
* ``build_embedder(dir)`` مع مجلد محدد **صريحاً** ومعطوب → استثناء صريح
  (Fail-Closed): السقوط الصامت إلى الوضع المعجمي هنا خداع للمستخدم.
* Pooling تلقائي: خرج 2D = متجه جملة جاهز (تصديرات BGE-M3 dense)؛
  خرج 3D = رموز → mean pooling افتراضياً أو CLS عند التحديد.
* ``encode_all``: تشفير دفعي مرة واحدة لكل نص + ذاكرة تخزين — لا إعادة
  تشفير لكل زوج داخل الـ DP.
"""

from __future__ import annotations

from pathlib import Path


class OnnxEmbedder:
    """غلاف ONNX Runtime لنموذج تضمين محلي متعدد اللغات."""

    def __init__(self, model_dir: str | Path, pooling: str = "auto") -> None:
        d = Path(model_dir)
        model_file = d / "model.onnx"
        if not model_file.exists():
            raise FileNotFoundError(
                f"لا يوجد نموذج ONNX محلي في {d} — وضع Local-First يمنع التنزيل؛ "
                "ضع ملف model.onnx + tokenizer.json في المجلد أو استخدم الوضع المعجمي."
            )
        if pooling not in {"auto", "mean", "cls"}:
            raise ValueError(f"pooling غير قانوني: {pooling!r}")
        import numpy as np
        from tokenizers import Tokenizer

        import onnxruntime as ort

        self._np = np
        self.pooling = pooling
        self.session = ort.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.input_names = {i.name for i in self.session.get_inputs()}
        self._cache: dict[str, "np.ndarray"] = {}

    def _encode_matrix(self, texts: list[str]):
        """شغّل النموذج مرة واحدة على دفعة نصوص — بلا ذاكرة (الطبقة الدنيا)."""
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
        if out.ndim == 2:
            # تصدير يُخرج متجه الجملة مباشرة (BGE-M3 dense وغيره) — بلا pooling
            emb = out
        elif out.ndim == 3:
            mask = attention[:, :, None].astype(np.float32)
            if self.pooling == "cls":
                emb = out[:, 0, :]
            else:  # auto / mean
                emb = (out * mask).sum(1) / np.clip(mask.sum(1), 1e-9, None)
        else:
            raise ValueError(f"خرج نموذج غير متوقع: ndim={out.ndim} — لا تخمين في التفسير")
        return emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)

    def encode_all(self, texts: list[str]):
        """شفّر كل نص **مرة واحدة** (دفعياً) وخزّن — استدعاء متكرر رخيص."""
        missing = [t for t in texts if t not in self._cache]
        if missing:
            matrix = self._encode_matrix(missing)
            for text, vec in zip(missing, matrix):
                self._cache[text] = vec
        np = self._np
        return np.stack([self._cache[t] for t in texts])

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.encode_all([a, b])
        return float((va * vb).sum())


def build_embedder(model_dir: str | None) -> OnnxEmbedder | None:
    """None = لا نموذج مطلوب (وضع معجمي). مجلد محدد ومعطوب = فشل صريح."""
    if not model_dir:
        return None
    try:
        return OnnxEmbedder(model_dir)
    except Exception as exc:  # noqa: BLE001 — Fail-Closed: لا سقوط صامت
        raise RuntimeError(
            f"فشل تحميل النموذج المحلي المحدد صراحةً ({model_dir}): {exc}\n"
            "الوضع المحلي يمنع المتابعة بنموذج آخر أو بلا نموذج بصمت — أصلح المجلد "
            "أو أزل local_onnx_model_dir لتعود للوضع المعجمي."
        ) from exc
