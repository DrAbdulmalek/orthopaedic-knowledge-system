-- مخطط قاعدة التوليف synthesis.db — منفصلة عمداً عن knowledge.db وcorrections.db:
-- القرارات الامتحانية (دمج كتب EN↔EN) حالة مستقلة عن الترجمة والتصحيح اللغوي.
-- كل وحدة تحمل معرف إثبات: [BOOK]_[CHAPTER]_P###_U###

CREATE TABLE IF NOT EXISTS sources (
    source_id   INTEGER PRIMARY KEY,
    book_code   TEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL CHECK (role IN ('spine', 'other')),
    chapter     TEXT NOT NULL,
    origin      TEXT NOT NULL,                -- مسار الملف المحلي الذي جاءت منه
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS units (
    unit_id      TEXT PRIMARY KEY,            -- MILLER_CH04_P112_U001
    source_id    INTEGER NOT NULL REFERENCES sources(source_id),
    kind         TEXT NOT NULL CHECK (kind IN ('body', 'caption', 'table_cell', 'footnote')),
    page_first   INTEGER NOT NULL CHECK (page_first > 0),
    page_last    INTEGER NOT NULL CHECK (page_last >= page_first),
    section_path TEXT,
    text         TEXT NOT NULL,
    text_norm    TEXT NOT NULL,
    seq          INTEGER NOT NULL             -- الترتيب داخل الكتاب
);
CREATE INDEX IF NOT EXISTS idx_units_source ON units(source_id, seq);

CREATE TABLE IF NOT EXISTS links (
    link_id        INTEGER PRIMARY KEY,
    spine_unit_id  TEXT NOT NULL REFERENCES units(unit_id),
    other_unit_id  TEXT NOT NULL REFERENCES units(unit_id),
    book_code      TEXT NOT NULL,
    score          REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    lexical        REAL NOT NULL,
    semantic       REAL,                      -- NULL في الوضع المعجمي الصرف
    decision       TEXT NOT NULL CHECK (decision IN ('DUPLICATE', 'DELTA', 'CONFLICT', 'UNLINKED')),
    reason         TEXT NOT NULL,
    UNIQUE (other_unit_id)                    -- كل وحدة غير العمود الفقري قرار واحد
);

CREATE TABLE IF NOT EXISTS deltas (
    delta_id     INTEGER PRIMARY KEY,
    unit_id      TEXT NOT NULL REFERENCES units(unit_id),
    anchor_unit  TEXT REFERENCES units(unit_id),  -- وحدة العمود الفقري المرساة (إن وجدت)
    new_facts    TEXT NOT NULL,                   -- JSON: أرقام/تصنيفات غير موجودة في العمود
    reason       TEXT NOT NULL,
    book_code    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id   INTEGER PRIMARY KEY,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN ('numbers', 'classification', 'recommendation')),
    spine_unit_id TEXT NOT NULL REFERENCES units(unit_id),
    other_unit_id TEXT NOT NULL REFERENCES units(unit_id),
    book_code     TEXT NOT NULL,
    spine_detail  TEXT NOT NULL,              -- JSON: الأرقام/النظام/التوصية من العمود
    other_detail  TEXT NOT NULL,              -- JSON: مقابلها من الكتاب الآخر
    status        TEXT NOT NULL DEFAULT 'BLOCKED' CHECK (status IN ('PROVEN', 'UNPROVEN', 'BLOCKED')),
    resolution    TEXT
);

CREATE TABLE IF NOT EXISTS blocked_log (
    block_id  INTEGER PRIMARY KEY,
    stage     TEXT NOT NULL,
    ref       TEXT NOT NULL,
    detail    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
