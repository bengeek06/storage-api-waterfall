# Documentation Storage Service

## 📚 Guides d'intégration

### [Intégration Service Identity](./IDENTITY_INTEGRATION.md)
Guide complet pour uploader et gérer les avatars utilisateur depuis le service Identity.

**Contenu :**
- Workflow d'upload en 2 étapes (presigned URL + PUT MinIO)
- Helper Python prêt à l'emploi ([`identity_helper.py`](./identity_helper.py))
- Stockage des métadonnées en DB
- Gestion des erreurs et validations
- Exemples de code complets

**Cas d'usage :** PATCH `/users/{id}` avec avatar multipart

---

## 🔗 Références rapides

### URLs du service
- **Development:** `http://localhost:5000`
- **Docker:** `http://storage-service:5000`

### Endpoints clés

| Endpoint | Méthode | Usage |
|----------|---------|-------|
| `/upload/presign` | POST | Obtenir URL pré-signée pour upload |
| `/list` | GET | Lister fichiers dans un bucket |
| `/metadata` | GET | Métadonnées d'un fichier |
| `/copy` | POST | Copier fichier entre buckets |
| `/lock` | POST | Verrouiller un fichier |
| `/unlock` | POST | Déverrouiller un fichier |
| `/versions` | GET | Lister versions d'un fichier |
| `/versions/commit` | POST | Créer nouvelle version |
| `/versions/{id}/approve` | POST | Approuver une version |

### Authentification

**Option 1 : Headers (backend-to-backend)**
```http
X-User-ID: {uuid}
X-Company-ID: {uuid}
```

**Option 2 : Cookie JWT (frontend)**
```http
Cookie: access_token={jwt_token}
```

---

## 📖 Documentation complète

- [OpenAPI Specification](../openapi.yml)
- [README principal](../README.md)
- [Configuration](../env.example)

---

## 🛠️ Helpers disponibles

### Python
- [`identity_helper.py`](./identity_helper.py) - Upload avatar utilisateur

### À venir
- Helper Node.js/TypeScript
- Helper pour service Project
- SDK client complet

---

## 💡 Besoin d'aide ?

1. Consulter l'[OpenAPI spec](../openapi.yml)
2. Vérifier les logs : `docker logs storage-service`
3. Tester avec curl :
   ```bash
   curl -X POST http://localhost:5000/upload/presign \
     -H "X-User-ID: your-uuid" \
     -H "X-Company-ID: your-uuid" \
     -H "Content-Type: application/json" \
     -d '{
       "bucket_type": "users",
       "bucket_id": "your-uuid",
       "logical_path": "test/file.txt"
     }'
   ```
