# Modèle de données recommandé

## Vue d'ensemble

Ce document décrit le modèle de données Postgres recommandé pour implémenter les user stories de gestion documentaire collaborative.

## Tables principales

### 1. Table `files`

Métadonnées principales des fichiers dans le système.

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('users', 'companies', 'projects')),
    bucket_id VARCHAR(255) NOT NULL,
    logical_path TEXT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    current_version_id UUID,
    source_file_id UUID REFERENCES files(id), -- Pour les copies/drafts
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    owner_id UUID NOT NULL,
    tags JSONB DEFAULT '[]'::jsonb,
    mime_type VARCHAR(255),
    size BIGINT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'upload_pending', 'pending_validation', 
        'approved', 'rejected', 'requires_revision', 'archived'
    )),
    
    -- Contraintes
    UNIQUE(bucket_type, bucket_id, logical_path),
    
    -- Index
    INDEX idx_files_bucket (bucket_type, bucket_id),
    INDEX idx_files_owner (owner_id),
    INDEX idx_files_status (status),
    INDEX idx_files_path (logical_path),
    INDEX idx_files_updated (updated_at)
);
```

### 2. Table `file_versions`

Historique des versions de chaque fichier.

```sql
CREATE TABLE file_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    object_key TEXT NOT NULL, -- Clé MinIO
    version_number INTEGER NOT NULL,
    size BIGINT NOT NULL,
    mime_type VARCHAR(255),
    checksum VARCHAR(64), -- SHA-256 optionnel
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    changelog TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    
    -- Contraintes
    UNIQUE(file_id, version_number),
    
    -- Index
    INDEX idx_file_versions_file (file_id),
    INDEX idx_file_versions_created_by (created_by),
    INDEX idx_file_versions_created_at (created_at)
);
```

### 3. Table `locks`

Système de verrouillage des fichiers.

```sql
CREATE TABLE locks (
    lock_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    locked_by UUID NOT NULL,
    locked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reason TEXT,
    forced BOOLEAN DEFAULT FALSE,
    
    -- Contraintes
    UNIQUE(file_id), -- Un seul lock par fichier
    
    -- Index
    INDEX idx_locks_file (file_id),
    INDEX idx_locks_user (locked_by),
    INDEX idx_locks_date (locked_at)
);
```

### 4. Table `validations`

Workflow de validation des versions.

```sql
CREATE TABLE validations (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES file_versions(version_id) ON DELETE CASCADE,
    state VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'approved', 'rejected')),
    requested_by UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_by UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    comment TEXT,
    require_new_version BOOLEAN DEFAULT FALSE,
    
    -- Index
    INDEX idx_validations_version (version_id),
    INDEX idx_validations_state (state),
    INDEX idx_validations_requested_by (requested_by),
    INDEX idx_validations_reviewed_by (reviewed_by)
);
```

### 5. Table `audit_logs`

Audit trail complet des actions.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL, -- 'file', 'version', 'lock', 'validation'
    entity_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    actor UUID NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    meta JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    
    -- Index
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_actor (actor),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_action (action)
);
```

## Vues utiles

### Vue des fichiers avec version courante

```sql
CREATE VIEW files_with_current_version AS
SELECT 
    f.*,
    fv.version_id as current_version_id,
    fv.version_number as current_version_number,
    fv.object_key as current_object_key,
    fv.checksum as current_checksum,
    fv.created_by as last_modified_by,
    l.lock_id IS NOT NULL as is_locked,
    l.locked_by,
    l.locked_at
FROM files f
LEFT JOIN file_versions fv ON f.current_version_id = fv.version_id
LEFT JOIN locks l ON f.id = l.file_id;
```

### Vue des validations en attente

```sql
CREATE VIEW pending_validations AS
SELECT 
    v.*,
    f.logical_path,
    f.filename,
    f.bucket_type,
    f.bucket_id,
    fv.version_number,
    fv.size,
    fv.changelog
FROM validations v
JOIN file_versions fv ON v.version_id = fv.version_id
JOIN files f ON fv.file_id = f.id
WHERE v.state = 'pending';
```

## Triggers recommandés

### Mise à jour automatique de `updated_at`

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_files_updated_at 
    BEFORE UPDATE ON files 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Audit automatique

```sql
CREATE OR REPLACE FUNCTION create_audit_log()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (entity_type, entity_id, action, actor, meta)
    VALUES (
        TG_TABLE_NAME,
        COALESCE(NEW.id, NEW.version_id, NEW.lock_id, NEW.validation_id),
        TG_OP,
        COALESCE(NEW.created_by, NEW.locked_by, NEW.requested_by),
        jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW))
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ language 'plpgsql';

-- Appliquer sur les tables critiques
CREATE TRIGGER files_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON files
    FOR EACH ROW EXECUTE FUNCTION create_audit_log();

CREATE TRIGGER locks_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON locks
    FOR EACH ROW EXECUTE FUNCTION create_audit_log();
```

## Contraintes et validations

### Règles métier importantes

1. **Un seul lock par fichier** : Géré par UNIQUE constraint
2. **Cohérence des versions** : current_version_id doit exister dans file_versions
3. **Buckets valides** : Validation via CHECK constraints
4. **Statuts cohérents** : États valides définis par CHECK constraints

### Performance

1. **Index composites** pour les requêtes fréquentes
2. **Partitioning** des audit_logs par date si volume important
3. **Archivage** des anciennes versions selon politique de rétention

## Migration recommandée

Créer les tables dans cet ordre pour respecter les contraintes :

1. `files` (sans current_version_id)
2. `file_versions`
3. `locks`
4. `validations`
5. `audit_logs`
6. Ajouter la contrainte `current_version_id` sur `files`
7. Créer les vues et triggers