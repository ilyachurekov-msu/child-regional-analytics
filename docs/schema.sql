BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE core.regions (
    region_id TEXT NOT NULL, 
    name TEXT NOT NULL, 
    federal_district TEXT NOT NULL, 
    okato_code TEXT, 
    oktmo_code TEXT, 
    valid_from DATE NOT NULL, 
    valid_to DATE, 
    CONSTRAINT pk_regions PRIMARY KEY (region_id)
);

CREATE TABLE core.sources (
    source_id UUID NOT NULL, 
    normalized_identifier TEXT NOT NULL, 
    source_type TEXT NOT NULL, 
    name TEXT NOT NULL, 
    url TEXT, 
    publisher TEXT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_sources PRIMARY KEY (source_id), 
    CONSTRAINT uq_sources_normalized_identifier UNIQUE (normalized_identifier)
);

CREATE TABLE core.topics (
    topic_id TEXT NOT NULL, 
    name TEXT NOT NULL, 
    parent_topic_id TEXT, 
    CONSTRAINT pk_topics PRIMARY KEY (topic_id), 
    CONSTRAINT fk_topics_parent_topic_id_topics FOREIGN KEY(parent_topic_id) REFERENCES core.topics (topic_id)
);

CREATE SCHEMA IF NOT EXISTS regional;

CREATE TABLE regional.import_batches (
    batch_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    checksum VARCHAR(64) NOT NULL, 
    parser_version TEXT NOT NULL, 
    raw_path TEXT NOT NULL, 
    rows_processed INTEGER NOT NULL, 
    errors INTEGER NOT NULL, 
    status TEXT NOT NULL, 
    CONSTRAINT pk_import_batches PRIMARY KEY (batch_id), 
    CONSTRAINT uq_import_batches_source_id UNIQUE (source_id, checksum, parser_version), 
    CONSTRAINT fk_import_batches_source_id_sources FOREIGN KEY(source_id) REFERENCES core.sources (source_id)
);

CREATE TABLE regional.indicators (
    indicator_id UUID NOT NULL, 
    code TEXT NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT NOT NULL, 
    topic_id TEXT NOT NULL, 
    unit TEXT NOT NULL, 
    direction TEXT NOT NULL, 
    methodology TEXT NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    CONSTRAINT pk_indicators PRIMARY KEY (indicator_id), 
    CONSTRAINT ck_indicators_direction CHECK (direction IN ('positive','negative','ambiguous')), 
    CONSTRAINT uq_indicators_code UNIQUE (code), 
    CONSTRAINT fk_indicators_topic_id_topics FOREIGN KEY(topic_id) REFERENCES core.topics (topic_id)
);

CREATE TABLE regional.data_quality_issues (
    issue_id UUID NOT NULL, 
    batch_id UUID NOT NULL, 
    indicator_id UUID, 
    region_id TEXT, 
    issue_type TEXT NOT NULL, 
    description TEXT NOT NULL, 
    resolution_status TEXT NOT NULL, 
    CONSTRAINT pk_data_quality_issues PRIMARY KEY (issue_id), 
    CONSTRAINT fk_data_quality_issues_batch_id_import_batches FOREIGN KEY(batch_id) REFERENCES regional.import_batches (batch_id), 
    CONSTRAINT fk_data_quality_issues_indicator_id_indicators FOREIGN KEY(indicator_id) REFERENCES regional.indicators (indicator_id), 
    CONSTRAINT fk_data_quality_issues_region_id_regions FOREIGN KEY(region_id) REFERENCES core.regions (region_id)
);

CREATE TABLE regional.indicator_values (
    value_id UUID NOT NULL, 
    indicator_id UUID NOT NULL, 
    region_id TEXT NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    value NUMERIC(24, 6), 
    source_id UUID NOT NULL, 
    batch_id UUID NOT NULL, 
    published_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    data_status TEXT NOT NULL, 
    is_current BOOLEAN NOT NULL, 
    revision_number INTEGER NOT NULL, 
    CONSTRAINT pk_indicator_values PRIMARY KEY (value_id), 
    CONSTRAINT uq_indicator_values_indicator_id UNIQUE (indicator_id, region_id, period_start, period_end, revision_number), 
    CONSTRAINT ck_indicator_values_period CHECK (period_end >= period_start), 
    CONSTRAINT ck_indicator_values_revision CHECK (revision_number > 0), 
    CONSTRAINT ck_indicator_values_status CHECK (data_status IN ('official','missing','provisional')), 
    CONSTRAINT ck_indicator_values_missing CHECK ((value IS NULL AND data_status = 'missing') OR (value IS NOT NULL AND data_status != 'missing')), 
    CONSTRAINT fk_indicator_values_indicator_id_indicators FOREIGN KEY(indicator_id) REFERENCES regional.indicators (indicator_id), 
    CONSTRAINT fk_indicator_values_region_id_regions FOREIGN KEY(region_id) REFERENCES core.regions (region_id), 
    CONSTRAINT fk_indicator_values_source_id_sources FOREIGN KEY(source_id) REFERENCES core.sources (source_id), 
    CONSTRAINT fk_indicator_values_batch_id_import_batches FOREIGN KEY(batch_id) REFERENCES regional.import_batches (batch_id)
);

CREATE UNIQUE INDEX uq_values_current ON regional.indicator_values (indicator_id, region_id, period_start, period_end) WHERE is_current;

CREATE INDEX ix_values_region_period ON regional.indicator_values (region_id, period_start);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

ALTER TABLE regional.import_batches ADD COLUMN original_checksum VARCHAR(64);

ALTER TABLE regional.import_batches ADD COLUMN original_path TEXT;

ALTER TABLE regional.indicator_values ALTER COLUMN published_at DROP NOT NULL;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;

