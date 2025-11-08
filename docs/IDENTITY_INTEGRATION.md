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

### 1️⃣ Obtenir une URL pré-signée (Upload)

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
  "logical_path": "/avatars/avatar.jpg",
  "content_type": "image/jpeg"
}
```

**Paramètres :**
- `bucket_type` : Toujours `"users"` pour les avatars
- `bucket_id` : UUID de l'utilisateur
- `logical_path` : Chemin logique (recommandé : `/avatars/avatar.jpg`)
- `content_type` : Type MIME du fichier (optionnel, mais recommandé)

**Réponse (200 OK) :**
```json
{
  "status": "success",
  "upload_url": "https://minio:9000/storage/users/6f9b3a34.../avatars/avatar.jpg?X-Amz-Signature=...",
  "expires_in": 900,
  "object_key": "users/6f9b3a34.../avatars/avatar.jpg",
  "file_id": "uuid-of-file-record"
}
```

**Erreurs possibles :**
- `400` : Validation error (bucket_id invalide, logical_path vide, etc.)
- `403` : Access denied (l'utilisateur ne peut pas écrire dans ce bucket)
- `500` : Server error (MinIO inaccessible)

---

### 2️⃣ Uploader le fichier sur MinIO

**Endpoint :**  
Utiliser l'URL retournée dans `upload_url` de la réponse précédente.

**Méthode :**
```http
PUT {upload_url}
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

### 3️⃣ Alternative : Upload via proxy

Si l'upload direct sur MinIO n'est pas possible (pare-feu, CORS, etc.), vous pouvez utiliser l'endpoint proxy :

**Endpoint :**
```http
POST /upload/proxy
```

**Headers :**
```http
X-User-ID: {user_uuid}
X-Company-ID: {company_uuid}
Content-Type: multipart/form-data
```

**Body (multipart/form-data) :**
```
bucket_type=users
bucket_id=6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1
logical_path=/avatars/avatar.jpg
file=@avatar.jpg
```

**Réponse (200 OK) :**
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "file_id": "uuid",
  "object_key": "users/6f9b3a34.../avatars/avatar.jpg",
  "version_id": "uuid-version",
  "size": 524288
}
```

**Avantages de l'upload proxy :**
- ✅ Pas besoin de deux requêtes (presign + PUT)
- ✅ Fonctionne même si MinIO n'est pas accessible directement
- ✅ Gestion automatique des erreurs

**Inconvénients :**
- ❌ Le fichier transite par le service Storage (plus lent)
- ❌ Charge CPU/mémoire sur le service Storage

---

### 4️⃣ Télécharger l'avatar (Download)

**Endpoint :**
```http
GET /download/presign?bucket_type=users&bucket_id={uuid}&logical_path=/avatars/avatar.jpg
```

**Headers :**
```http
X-User-ID: {user_uuid}
X-Company-ID: {company_uuid}
```

**Réponse (200 OK) :**
```json
{
  "status": "success",
  "download_url": "https://minio:9000/storage/users/6f9b3a34.../avatars/avatar.jpg?X-Amz-Signature=...",
  "expires_in": 900,
  "file_id": "uuid",
  "filename": "avatar.jpg",
  "size": 524288
}
```

**Utilisation :**
Le frontend peut ensuite :
1. Utiliser `download_url` directement dans une balise `<img src="...">`
2. Ou télécharger le fichier avec `fetch(download_url)`

**Alternative : Proxy download**
```http
GET /download/proxy?bucket_type=users&bucket_id={uuid}&logical_path=/avatars/avatar.jpg
```

Retourne directement le fichier binaire avec les headers appropriés.

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

### Solution 1 : URL pré-signée (RECOMMANDÉ)

Lorsque le frontend demande `GET /users/{user_id}`, Identity peut :

1. Récupérer le triplet `(bucket_type, bucket_id, logical_path)` de la DB
2. Appeler Storage pour obtenir une URL de download
3. Retourner cette URL au frontend

**Appel vers Storage :**
```python
import requests

response = requests.get(
    f"http://storage-service:5000/download/presign",
    params={
        "bucket_type": "users",
        "bucket_id": user.id,
        "logical_path": user.avatar_logical_path
    },
    headers={
        "X-User-ID": user.id,
        "X-Company-ID": user.company_id
    }
)

if response.status_code == 200:
    avatar_url = response.json()["download_url"]
    # Retourner au frontend
```

**Réponse au frontend :**
```json
{
  "id": "uuid",
  "username": "john.doe",
  "avatar_url": "https://minio:9000/storage/users/.../avatar.jpg?X-Amz-Signature=..."
}
```

Le frontend peut alors utiliser directement cette URL :
```html
<img src="{{ avatar_url }}" alt="Avatar">
```

**Avantages :**
- ✅ Le frontend accède directement à MinIO (performances maximales)
- ✅ Décharge le service Identity
- ✅ URLs temporaires (sécurité)

**Inconvénients :**
- ❌ Nécessite que MinIO soit accessible depuis le navigateur
- ❌ URLs expirent (900s par défaut)

### Solution 2 : Proxy via Identity

Le service Identity peut créer son propre endpoint :

```http
GET /users/{user_id}/avatar
```

Qui :
1. Lit le triplet en DB
2. Appelle `/download/proxy` du Storage Service
3. Stream le fichier au frontend

**Implémentation Python :**
```python
@app.route('/users/<user_id>/avatar')
def get_user_avatar(user_id):
    user = User.query.get(user_id)
    if not user or not user.avatar_logical_path:
        abort(404)
    
    # Appel au Storage Service
    response = requests.get(
        f"http://storage-service:5000/download/proxy",
        params={
            "bucket_type": "users",
            "bucket_id": user.id,
            "logical_path": user.avatar_logical_path
        },
        headers={
            "X-User-ID": user.id,
            "X-Company-ID": user.company_id
        },
        stream=True
    )
    
    if response.status_code != 200:
        abort(response.status_code)
    
    # Stream le fichier
    return Response(
        response.iter_content(chunk_size=8192),
        content_type=response.headers['Content-Type'],
        headers={
            'Content-Disposition': response.headers.get('Content-Disposition')
        }
    )
```

**Utilisation frontend :**
```html
<img src="/users/{{ user_id }}/avatar" alt="Avatar">
```

**Avantages :**
- ✅ URLs stables (pas d'expiration)
- ✅ MinIO n'a pas besoin d'être accessible depuis le navigateur
- ✅ Contrôle total sur les permissions

**Inconvénients :**
- ❌ Le fichier transite par Identity (charge CPU/réseau)
- ❌ Latence supplémentaire

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
- 🗑️ Utiliser l'endpoint `DELETE /delete` du Storage Service avec `physical=true`

**Exemple de suppression :**
```python
import requests

# Supprimer l'ancien avatar avant d'uploader le nouveau
if user.avatar_logical_path:
    requests.delete(
        "http://storage-service:5000/delete",
        json={
            "bucket_type": "users",
            "bucket_id": str(user.id),
            "logical_path": user.avatar_logical_path,
            "physical": True  # Suppression définitive
        },
        headers={
            "X-User-ID": str(user.id),
            "X-Company-ID": str(user.company_id)
        }
    )
```

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
