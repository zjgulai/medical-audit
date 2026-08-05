-- remediation_items: Sprint 5 整改独立表
-- 依赖 audit_findings 表（可选外键，允许独立创建整改事项）
CREATE TABLE IF NOT EXISTS remediation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_key VARCHAR(128) NOT NULL UNIQUE,
    audit_finding_id UUID REFERENCES audit_findings(id) ON DELETE SET NULL,
    project_key VARCHAR(128),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status VARCHAR(48) NOT NULL DEFAULT 'pending-rectification',
    responsible_dept VARCHAR(256),
    responsible_person VARCHAR(128),
    due_date TIMESTAMPTZ,
    rectification_note TEXT NOT NULL DEFAULT '',
    acceptance_note TEXT NOT NULL DEFAULT '',
    attachment_count INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    closed_by TEXT,
    closed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_remediation_items_finding ON remediation_items(audit_finding_id);
CREATE INDEX IF NOT EXISTS idx_remediation_items_status ON remediation_items(status);
CREATE INDEX IF NOT EXISTS idx_remediation_items_project ON remediation_items(project_key);
