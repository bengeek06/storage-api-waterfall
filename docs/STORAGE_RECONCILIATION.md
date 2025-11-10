# Storage Reconciliation

## Problème de cohérence MinIO ↔ Database

Des incohérences peuvent survenir si :
- Un upload échoue après l'insertion DB mais avant MinIO
- Un fichier est supprimé manuellement de MinIO
- Une transaction DB est rollback après upload MinIO
- Un crash système pendant une opération

## Solutions mises en place

### 1. Détection à la lecture (temps réel)
✅ Implémenté dans `BucketDownloadProxyResource.get()`

Quand un fichier n'existe pas dans MinIO :
- Retourne 404 au client
- Log un warning avec file_id et version_id
- **Marque automatiquement la version comme "corrupted"**

### 2. Script de réconciliation périodique
✅ Script disponible : `scripts/reconcile_storage.py`

**Usage :**
```bash
# Rapport seulement (recommandé d'abord)
python scripts/reconcile_storage.py --report-only

# Avec correction automatique
python scripts/reconcile_storage.py --fix
```

**Configuration cron (exécution quotidienne à 2h du matin) :**
```bash
# Ajouter dans crontab -e
0 2 * * * cd /path/to/storage_service && /usr/bin/python3 scripts/reconcile_storage.py --fix >> /var/log/storage_reconciliation.log 2>&1
```

**Que fait le script :**
1. **DB orphans** : Vérifie chaque FileVersion dans la DB
   - Si le fichier n'existe pas dans MinIO → marque comme "corrupted"
2. **MinIO orphans** : Liste tous les objets MinIO
   - Si aucune entrée DB correspondante → log pour nettoyage manuel
3. **Rapport** : Génère des statistiques complètes

### 3. Prévention à l'upload

**Pattern actuel (transactionnel) :**
```python
# ✅ Bon ordre :
1. Créer/update DB record
2. Upload vers MinIO
3. Commit DB transaction

# En cas d'échec à l'étape 2 → rollback DB automatique
# En cas d'échec à l'étape 3 → fichier orphelin dans MinIO (détecté par le script)
```

## Monitoring

### Métriques à surveiller
- Nombre de versions "corrupted" (alerte si > seuil)
- Logs avec `FILE_NOT_FOUND_IN_STORAGE`
- Rapport quotidien du script de réconciliation

### Requête de monitoring
```sql
-- Fichiers corrompus
SELECT COUNT(*) FROM file_versions WHERE status = 'corrupted';

-- Fichiers corrompus par bucket
SELECT 
    sf.bucket_type,
    COUNT(*) as corrupted_count
FROM file_versions fv
JOIN storage_files sf ON fv.file_id = sf.id
WHERE fv.status = 'corrupted'
GROUP BY sf.bucket_type;
```

## Stratégie de nettoyage

### Fichiers corrompus (DB orphans)
Les versions marquées "corrupted" peuvent être :
1. **Réuploadées** par l'utilisateur (nouvelle version)
2. **Supprimées** après X jours (via script de purge)

### Fichiers orphelins MinIO
**⚠️ Attention :** Ne pas supprimer automatiquement !

Raisons possibles :
- Upload en cours
- Backup manuel
- Migration de données

**Approche recommandée :**
1. Le script log les orphelins
2. Investigation manuelle
3. Suppression après confirmation

```bash
# Commande pour supprimer un orphelin MinIO
mc rm minio/staging-storage/users/uuid/path/file
```

## FAQ

**Q: Pourquoi ne pas vérifier au démarrage du service ?**
- Temps de démarrage trop long (milliers de fichiers)
- Race conditions avec plusieurs instances
- Peut bloquer le déploiement

**Q: Que faire si beaucoup de corrupted apparaissent ?**
1. Vérifier les logs pour la cause racine
2. Vérifier la santé de MinIO
3. Vérifier les transactions DB (rollback anormal ?)

**Q: Peut-on avoir des fichiers en double ?**
- Non, `object_key` est unique dans MinIO
- `file_id + version_number` est unique en DB

**Q: Comment restaurer un fichier corrompu ?**
- Si backup MinIO existe → restaurer puis update DB
- Sinon → demander à l'utilisateur de réuploader
