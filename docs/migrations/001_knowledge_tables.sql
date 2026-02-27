-- Knowledge rules table
CREATE TABLE IF NOT EXISTS knowledge_rules (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('sql_pattern', 'domain_term', 'business_logic')),
    rule_text TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    source_question TEXT,
    source_correction TEXT,
    created_by BIGINT,
    approved_by BIGINT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_rules_status ON knowledge_rules(status);

-- Name aliases table
CREATE TABLE IF NOT EXISTS name_aliases (
    id SERIAL PRIMARY KEY,
    alias TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('school', 'region', 'district')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_name_aliases_status ON name_aliases(status);
