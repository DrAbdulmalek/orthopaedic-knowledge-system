-- مخطط القاعدة المعرفية الموحدة (knowledge.db)
-- كل سجل يحمل Provenance وحالة إلزامية: PROVEN | UNPROVEN | BLOCKED

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS books (
    book_id   INTEGER PRIMARY KEY,
    book_code TEXT NOT NULL UNIQUE,             -- CAMPBELL
    title_en  TEXT, title_ar TEXT,
    edition   TEXT, year INTEGER, isbn TEXT,
    license   TEXT DEFAULT 'owned-copy',
    notes     TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id    INTEGER PRIMARY KEY,
    book_id   INTEGER NOT NULL REFERENCES books(book_id),
    lang      TEXT NOT NULL CHECK (lang IN ('en','ar')),
    chapter   TEXT NOT NULL,                   -- CH04
    file_path TEXT, file_hash TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (book_id, lang, chapter)
);

-- كل جملة: معرف الإثبات الإلزامي [BOOK]_[CHAPTER]_[PAGE]_[SENTENCE_ID]
-- نفس المعرف يُستخدم للغتين (الترقيم لكل لغة مستقل) ويميزهما عمود lang
CREATE TABLE IF NOT EXISTS segments (
    segment_id   INTEGER PRIMARY KEY,
    sentence_id  TEXT NOT NULL,
    lang         TEXT NOT NULL CHECK (lang IN ('en','ar')),
    doc_id       INTEGER NOT NULL REFERENCES documents(doc_id),
    text         TEXT NOT NULL,
    text_norm    TEXT NOT NULL DEFAULT '',
    page         INTEGER NOT NULL CHECK (page > 0),
    bbox_json    TEXT,
    section_path TEXT,
    kind         TEXT NOT NULL DEFAULT 'body'
                 CHECK (kind IN ('body','caption','table_cell','footnote')),
    para_index   INTEGER,
    sent_index   INTEGER,
    UNIQUE (sentence_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_segments_norm ON segments(lang, text_norm);

CREATE TABLE IF NOT EXISTS alignments (
    alignment_id  INTEGER PRIMARY KEY,
    src_refs      TEXT NOT NULL,               -- JSON: ["CAMPBELL_CH04_P112_S005", ...]
    tgt_refs      TEXT NOT NULL,
    book_code     TEXT,
    align_type    TEXT NOT NULL
                  CHECK (align_type IN ('1:1','1:2','1:3','2:1','3:1','UNALIGNED')),
    confidence    REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    confidence_breakdown TEXT,                 -- JSON مفكك
    status        TEXT NOT NULL DEFAULT 'UNPROVEN'
                  CHECK (status IN ('PROVEN','UNPROVEN','BLOCKED')),
    reviewer      TEXT, reviewed_at TEXT, notes TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_align_status ON alignments(status);

-- الطبقة المفهومية (ISO 704/1087): المفهوم تجريد، والتسميات أدلة عليه
CREATE TABLE IF NOT EXISTS concepts (
    concept_id      TEXT PRIMARY KEY,          -- C-000001
    definition      TEXT,
    definition_lang TEXT DEFAULT 'en',
    specialty       TEXT,                      -- التخصص: Hip Surgery, Trauma...
    status          TEXT NOT NULL DEFAULT 'UNPROVEN'
                    CHECK (status IN ('PROVEN','UNPROVEN','BLOCKED')),
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS terms (
    term_id        INTEGER PRIMARY KEY,
    concept_id     TEXT NOT NULL REFERENCES concepts(concept_id),
    lang           TEXT NOT NULL CHECK (lang IN ('en','ar')),
    term_text      TEXT NOT NULL,
    term_norm      TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'synonym'
                   CHECK (role IN ('preferred','synonym')),
    term_type      TEXT NOT NULL DEFAULT 'fullForm'
                   CHECK (term_type IN ('fullForm','shortForm','abbreviation','variant')),
    -- طبقة الترجيح السوري: 1.0 = سوري معتمد، والبقية Contextual Synonyms
    dialect_weight REAL NOT NULL DEFAULT 0.0,
    context_note   TEXT,
    source         TEXT,                       -- count=3 | cooccur=2 | CORRECTION:5 | GLOSSARY:file.csv
    alignment_id   INTEGER,                    -- مرجع provenance ناعم (بلا FK — قد يكون أرشيفي)
    confidence     REAL,
    status         TEXT NOT NULL DEFAULT 'UNPROVEN'
                   CHECK (status IN ('PROVEN','UNPROVEN','BLOCKED')),
    reviewer       TEXT, reviewed_at TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (concept_id, lang, term_norm)
);
CREATE INDEX IF NOT EXISTS idx_terms_norm   ON terms(lang, term_norm);
CREATE INDEX IF NOT EXISTS idx_terms_role   ON terms(role, dialect_weight DESC);

-- أعلام ضمان الجودة
CREATE TABLE IF NOT EXISTS qa_flags (
    flag_id      INTEGER PRIMARY KEY,
    alignment_id INTEGER REFERENCES alignments(alignment_id),
    flag_type    TEXT NOT NULL CHECK (flag_type IN
                 ('LOW_CONFIDENCE','SUSPECTED_OMISSION','SUSPECTED_ADDITION',
                  'TERM_CONFLICT','BIDIRECTIONAL_MISMATCH')),
    detail       TEXT,
    resolved     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- سجل الرفض الفشل-الآمن (يملؤه fail_closed.block_item)
CREATE TABLE IF NOT EXISTS qa_blocks (
    block_id    INTEGER PRIMARY KEY,
    entity      TEXT NOT NULL,
    entity_key  TEXT NOT NULL,
    stage       TEXT NOT NULL,
    reason      TEXT NOT NULL,
    detail_json TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
