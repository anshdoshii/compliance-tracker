# ComplianceOS — Database Schema

All tables use PostgreSQL. All timestamps are UTC. UUIDs as primary keys.

## users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('ca', 'smb')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## ca_profiles
```sql
CREATE TABLE ca_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    icai_number VARCHAR(20) UNIQUE,
    firm_name VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    gstin VARCHAR(15),
    plan VARCHAR(20) DEFAULT 'starter' CHECK (plan IN ('starter','growth','pro','firm')),
    plan_client_limit INTEGER DEFAULT 10,
    plan_expires_at TIMESTAMPTZ,
    razorpay_subscription_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## smb_profiles
```sql
CREATE TABLE smb_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    company_type VARCHAR(50),
    gstin VARCHAR(15),
    pan VARCHAR(10),
    turnover_range VARCHAR(20),
    employee_count_range VARCHAR(20),
    sectors TEXT[],
    states TEXT[],
    gst_registered BOOLEAN DEFAULT FALSE,
    gst_composition BOOLEAN DEFAULT FALSE,
    has_factory BOOLEAN DEFAULT FALSE,
    import_export BOOLEAN DEFAULT FALSE,
    is_listed BOOLEAN DEFAULT FALSE,
    standalone_plan VARCHAR(20) DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## ca_client_links
```sql
CREATE TABLE ca_client_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_id UUID NOT NULL REFERENCES ca_profiles(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES smb_profiles(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','active','removed')),
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    removed_at TIMESTAMPTZ,
    UNIQUE(ca_id, client_id)
);
```

## compliance_items (master catalogue)
```sql
CREATE TABLE compliance_items (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    compliance_type VARCHAR(50) NOT NULL,
    authority VARCHAR(100),
    frequency VARCHAR(20),
    due_day INTEGER,
    due_day_rule VARCHAR(255),
    applicable_conditions JSONB,
    penalty_per_day INTEGER,
    max_penalty INTEGER,
    description TEXT,
    document_checklist TEXT[],
    ca_action_required BOOLEAN DEFAULT TRUE,
    client_action_required TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## client_compliance_items
```sql
CREATE TABLE client_compliance_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES smb_profiles(id) ON DELETE CASCADE,
    ca_id UUID REFERENCES ca_profiles(id),
    compliance_item_id VARCHAR(100) NOT NULL REFERENCES compliance_items(id),
    financial_year VARCHAR(10) NOT NULL,
    period VARCHAR(20),
    due_date DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN (
        'pending','in_progress','waiting_on_client','filed','not_applicable','overdue'
    )),
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## tasks
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_id UUID NOT NULL REFERENCES ca_profiles(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES smb_profiles(id) ON DELETE CASCADE,
    compliance_item_id UUID REFERENCES client_compliance_items(id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    assigned_to VARCHAR(10) CHECK (assigned_to IN ('ca','client')),
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN (
        'pending','in_progress','waiting_on_client','done','cancelled'
    )),
    due_date DATE,
    completed_at TIMESTAMPTZ,
    created_by VARCHAR(10) CHECK (created_by IN ('ca','client','system')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## documents
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES smb_profiles(id) ON DELETE CASCADE,
    ca_id UUID REFERENCES ca_profiles(id),
    task_id UUID REFERENCES tasks(id),
    compliance_item_id UUID REFERENCES client_compliance_items(id),
    file_name VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    r2_key VARCHAR(500) NOT NULL UNIQUE,
    uploaded_by VARCHAR(10) CHECK (uploaded_by IN ('ca','client')),
    document_type VARCHAR(50),
    financial_year VARCHAR(10),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## messages
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_id UUID NOT NULL REFERENCES ca_profiles(id),
    client_id UUID NOT NULL REFERENCES smb_profiles(id),
    sender_role VARCHAR(10) NOT NULL CHECK (sender_role IN ('ca','client')),
    content TEXT NOT NULL,
    attached_document_id UUID REFERENCES documents(id),
    linked_task_id UUID REFERENCES tasks(id),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_thread ON messages(ca_id, client_id);
```

## invoices
```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_id UUID NOT NULL REFERENCES ca_profiles(id),
    client_id UUID NOT NULL REFERENCES smb_profiles(id),
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    line_items JSONB NOT NULL,
    subtotal INTEGER NOT NULL,
    gst_rate INTEGER DEFAULT 18,
    gst_amount INTEGER NOT NULL,
    total_amount INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','sent','paid','overdue','cancelled')),
    due_date DATE,
    razorpay_payment_link_id VARCHAR(100),
    razorpay_payment_link_url VARCHAR(500),
    pdf_r2_key VARCHAR(500),
    sent_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## health_scores
```sql
CREATE TABLE health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES smb_profiles(id),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    breakdown JSONB,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_health_scores_client ON health_scores(client_id);
```

## Key relationship summary
- users (1) → (1) ca_profiles OR smb_profiles
- ca_profiles (M) ←→ (M) smb_profiles via ca_client_links
- tasks, messages, invoices all hang off the ca_id + client_id pair
- documents attach to client_id + optionally task_id or compliance_item_id
- health_scores are daily snapshots per client
