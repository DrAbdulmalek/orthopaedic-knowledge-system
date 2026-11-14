"""منظومة المعرفة والترجمة العظمية — Orthopaedic Knowledge & Translation System.

Local-First EN–AR sentence alignment and concept-oriented terminology
knowledge base for orthopaedic books. Everything runs locally on the
translator's machine (Manjaro); no component talks to the network.

المبادئ غير القابلة للتفاوض:
1. Local-First بالكامل — صفر اتصالات سحابية.
2. Fail-Closed — أي بيانات تالفة تُرفض وتُسجَّل BLOCKED، لا تخمين.
3. Provenance — كل جملة/مصطلح تحمل معرفاً: [BOOK]_[CHAPTER]_[PAGE]_[SENT].
4. تصنيف إلزامي — PROVEN / UNPROVEN / BLOCKED.
5. ترجيح سوري — المصطلح السوري المعتمد مفضّل والبقية Contextual Synonyms.
6. حللة تصحيح مستمرة — corrections.db يُطبَّق آلياً على المعالجات القادمة.
"""

__version__ = "0.3.1"
