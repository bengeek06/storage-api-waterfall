# Intégration Service Identity - Upload Avatar

## Vue d'ensemble

Ce document explique comment le service **Identity** doit interagir avec le **Storage Service** pour uploader et gérer les avatars utilisateur.

---

## 🎯 Cas d'usage : Upload d'avatar

Lorsqu'un utilisateur met à jour son avatar via `PATCH /users/{user_id}`, le service Identity doit :

1. **Obtenir une URL pré-signée** du Storage Service
2. **Uploader le fichier** directement sur MinIO via cette URL
3. **Stocker la référence** dans la table `users` d'Identity
4. **Retourner l'URL** au frontend pour affichage

---

## 📡 Endpoints Storage à utiliser

### URL du service
```
http://storage-service:5000
```

### 1️⃣ Obtenir une URL pré-signée

**Endpoint :**
```http
POST /upload/presign
```

**Headers :**
```http
X-User-ID: {user_uuid}
X-Company-ID: {company_uuid}
Content-Type: application/json
```

> **Note :** Si vous avez un JWT dans un cookie `access_token`, vous pouvez l'utiliser à la place des headers `X-User-ID` et `X-Company-ID`.

**Body (JSON) :**
```json
{
  "bucket_type": "users",
  "bucket_id": "6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1",
  "logical_path": "avatars/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1.jpg",
  "expires_in": 3600
}
```

**Paramètres :**
- `bucket_type` : Toujours `"users"` pour les avatars
- `bucket_id` : UUID de l'utilisateur
- `logical_path` : Chemin logique (recommandé : `avatars/{user_id}.{extension}`)
- `expires_in` : Durée de validité de l'URL en secondes (min: 300, max: 86400, défaut: 3600)

**Réponse (200 OK) :**
```json
{
  "url": "http://minio:9000/waterfall-storage/users/.../1?X-Amz-Algorithm=...",
  "object_key": "users/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1/avatars/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1.jpg/1",
  "expires_in": 3600,
  "expires_at": "2025-11-08T11:30:00Z"
}
```

**Erreurs possibles :**
- `400` : Validation error (bucket_id invalide, logical_path vide, etc.)
- `403` : Access denied (l'utilisateur ne peut pas écrire dans ce bucket)
- `500` : Server error (MinIO inaccessible)

---

### 2️⃣ Uploader le fichier sur MinIO

**Endpoint :**  
Utiliser l'URL retournée dans `url` de la réponse précédente.

**Méthode :**
```http
PUT {presigned_url}
Content-Type: image/jpeg
Content-Length: {file_size}

{binary_data}
```

**Important :**
- Utiliser la méthode **PUT** (pas POST)
- Le `Content-Type` doit correspondre au type MIME du fichier
- Envoyer le binaire brut du fichier

**Réponse MinIO (200 OK) :**
```
(vide, juste le status 200)
```

**Erreurs possibles :**
- `403` : URL expirée ou signature invalide
- `413` : Fichier trop volumineux
- `500` : Erreur MinIO

---

## 💾 Stockage dans Identity

### Option 1 : Stocker le triplet (RECOMMANDÉ)

Créer une table `user_files` ou ajouter des colonnes à `users` :

```sql
ALTER TABLE users ADD COLUMN avatar_bucket_type VARCHAR(20) DEFAULT 'users';
ALTER TABLE users ADD COLUMN avatar_bucket_id UUID;
ALTER TABLE users ADD COLUMN avatar_logical_path TEXT;
```

**Exemple de valeurs :**
```sql
UPDATE users 
SET 
  avatar_bucket_type = 'users',
  avatar_bucket_id = '6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1',
  avatar_logical_path = 'avatars/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1.jpg'
WHERE id = '6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1';
```

**Avantages :**
- ✅ Flexible : fonctionne si le Storage Service change d'architecture
- ✅ Portable : pas de dépendance à une URL absolue
- ✅ Permet de reconstruire l'URL à la demande

### Option 2 : Stocker l'object_key (SIMPLE)

```sql
ALTER TABLE users ADD COLUMN avatar_object_key TEXT;
```

**Exemple :**
```sql
UPDATE users 
SET avatar_object_key = 'users/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1/avatars/6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1.jpg/1'
WHERE id = '6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1';
```

**Avantages :**
- ✅ Une seule colonne
- ✅ Référence exacte au fichier versionné

---

## 🖼️ Affichage de l'avatar (Frontend)

Pour le moment, le Storage Service n'expose **pas encore** d'endpoint public de download.

### Solution temporaire : URL pré-signée

Lorsque le frontend demande `GET /users/{user_id}`, Identity peut :

1. Récupérer le triplet ou l'object_key de la DB
2. Appeler Storage pour obtenir une URL de download (à implémenter)
3. Retourner cette URL au frontend

**Endpoint à venir dans Storage :**
```http
GET /download/presign?bucket_type=users&bucket_id={uuid}&logical_path=avatars/...
```

### Solution recommandée : Proxy via Identity

Le service Identity peut créer son propre endpoint :

```http
GET /users/{user_id}/avatar
```

Qui :
1. Lit le triplet/object_key en DB
2. Génère une URL pré-signée via Storage (quand l'endpoint sera disponible)
3. Fait un **redirect 302** vers l'URL pré-signée
4. Ou stream le fichier directement

---

## 🔄 Workflow complet

```
┌─────────────┐
│  Frontend   │
│  (Browser)  │
└──────┬──────┘
       │
       │ PATCH /users/{id} (multipart avatar)
       ▼
┌─────────────────────┐
│  Identity Service   │
│  Port 5001          │
└──────┬──────────────┘
       │
       │ 1️⃣ POST /upload/presign
       ▼
┌─────────────────────┐
│  Storage Service    │
│  Port 5000          │
└──────┬──────────────┘
       │
       │ 2️⃣ Retourne presigned_url
       ▼
┌─────────────────────┐
│  Identity Service   │
└──────┬──────────────┘
       │
       │ 3️⃣ PUT {presigned_url} (binary)
       ▼
┌─────────────────────┐
│      MinIO          │
│  Object Storage     │
└──────┬──────────────┘
       │
       │ 4️⃣ 200 OK
       ▼
┌─────────────────────┐
│  Identity Service   │
│  - Save to DB       │
│  - Return response  │
└──────┬──────────────┘
       │
       │ 5️⃣ 200 OK {user_data}
       ▼
┌─────────────┐
│  Frontend   │
└─────────────┘
```

---

## 🛠️ Helper Python

Voir le fichier [`identity_helper.py`](./identity_helper.py) pour un exemple complet d'implémentation avec :
- Gestion d'erreurs
- Retry automatique
- Logging
- Timeout configurables
- Support multipart/form-data

---

## ⚠️ Points d'attention

### Sécurité
- ✅ Toujours vérifier que `user_id` du JWT correspond à l'utilisateur modifié
- ✅ Valider le type MIME du fichier (autoriser uniquement image/jpeg, image/png, image/webp)
- ✅ Limiter la taille du fichier (recommandé : 5 MB max pour avatars)

### Performance
- ⚡ L'upload direct sur MinIO évite de faire transiter le fichier par Identity
- ⚡ Les URLs pré-signées expirent (défaut 1h) : les générer à la demande
- ⚡ Considérer un cache Redis pour les URLs pré-signées si forte volumétrie

### Gestion des versions
- 📦 Le Storage Service versione automatiquement les fichiers
- 📦 Chaque upload crée une nouvelle version (suffixe `/1`, `/2`, etc.)
- 📦 L'object_key retourné inclut le numéro de version

### Nettoyage
- 🗑️ Prévoir un job pour supprimer les anciennes versions d'avatar
- 🗑️ Endpoint `/delete` du Storage Service (à implémenter)

---

## 📞 Support

En cas de problème :
1. Vérifier les logs du Storage Service
2. Vérifier la connectivité MinIO
3. Tester l'endpoint avec `curl` ou Postman
4. Consulter l'OpenAPI : [`openapi.yml`](../openapi.yml)

---

## 🔗 Liens utiles

- [OpenAPI Specification](../openapi.yml)
- [README principal](../README.md)
- [Helper Python](./identity_helper.py)
