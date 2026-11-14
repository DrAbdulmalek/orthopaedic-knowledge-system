-- قاعدة التصحيحات corrections.db — منفصلة عن القاعدة المعرفية عمداً.
-- المبدأ 6: أي تعديل بشري يُحفظ هنا كـ "قاعدة" تُطبَّق آلياً لاحقاً (Auto-apply).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS corrections (
    correction_id INTEGER PRIMARY KEY,
    entity        TEXT NOT NULL CHECK (entity IN ('alignment','term','concept','segment','conflict','delta')),
    -- مفتاح المطابقة للإعادة: exact_id (المعرف حرفياً) أو norm_term (بالمصطلح المطبَّع)
    match_rule    TEXT NOT NULL DEFAULT 'exact_id'
                  CHECK (match_rule IN ('exact_id','norm_term')),
    entity_key    TEXT NOT NULL,               -- A-000012 | avascular necrosis | C-000001
    field         TEXT NOT NULL,               -- ar_preferred | status | definition ...
    old_value     TEXT,
    new_value     TEXT NOT NULL,
    reviewer      TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS correction_applications (
    application_id INTEGER PRIMARY KEY,
    correction_id  INTEGER NOT NULL REFERENCES corrections(correction_id),
    target_entity  TEXT NOT NULL,
    target_key     TEXT NOT NULL,
    result         TEXT NOT NULL CHECK (result IN ('APPLIED','SKIPPED','BLOCKED')),
    detail         TEXT,
    applied_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_corr_lookup ON corrections(entity, match_rule, entity_key);
