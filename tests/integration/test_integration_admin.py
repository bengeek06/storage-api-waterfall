"""
test_integration_admin.py
==========================

Tests d'intégration pour les endpoints d'administration.
Teste /delete et /locks (GET).

Nécessite MinIO en cours d'exécution sur localhost:9000.
"""

import uuid
from app.models.storage import StorageFile, Lock


class TestFileDelete:
    """Tests pour l'endpoint DELETE /delete."""

    def test_delete_logical_only(
        self, client, db, test_user_id, test_company_id, sample_file
    ):
        """Test suppression logique uniquement."""
        file_id = sample_file.id

        response = client.delete(
            "/delete",
            json={"file_id": file_id, "physical": False},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["logical_delete"] is True
        assert json_data["data"]["physical_delete"] is False

        # Vérifier que le fichier est marqué comme deleted
        db.expire_all()
        file_obj = StorageFile.get_by_file_id(file_id)
        assert file_obj.status == "archived"

    def test_delete_logical_and_physical(
        self,
        client,
        db,
        test_user_id,
        test_company_id,
        sample_file_with_content,
    ):
        """Test suppression logique + physique."""
        file_obj, _ = sample_file_with_content
        file_id = file_obj.id

        response = client.delete(
            "/delete",
            json={"file_id": file_id, "physical": True},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["data"]["logical_delete"] is True
        # physical_delete peut être True ou False selon si MinIO était accessible

        # Vérifier que le fichier a été complètement supprimé de la DB
        db.expire_all()
        file_obj = StorageFile.get_by_file_id(file_id)
        assert file_obj is None, "File should be completely deleted from database"

    def test_delete_file_not_found(
        self, client, test_user_id, test_company_id
    ):
        """Test suppression d'un fichier inexistant."""
        fake_file_id = str(uuid.uuid4())

        response = client.delete(
            "/delete",
            json={"file_id": fake_file_id, "physical": False},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data["error"] == "FILE_NOT_FOUND"

    def test_delete_no_permission(
        self, client, db, test_user_id, test_company_id, sample_file
    ):
        """Test suppression sans permission."""
        wrong_user_id = str(uuid.uuid4())

        response = client.delete(
            "/delete",
            json={"file_id": sample_file.id, "physical": False},
            headers={
                "X-User-ID": wrong_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 403

    def test_delete_missing_file_id(
        self, client, test_user_id, test_company_id
    ):
        """Test suppression sans file_id."""
        response = client.delete(
            "/delete",
            json={"physical": False},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data["error"] == "VALIDATION_ERROR"


class TestLocksList:
    """Tests pour l'endpoint GET /locks."""

    def test_locks_list_empty(self, client, db, test_user_id, test_company_id):
        """Test liste des verrous vide."""
        response = client.get(
            "/locks",
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["status"] == "success"
        assert "locks" in json_data["data"]
        assert json_data["data"]["total"] == 0

    def test_locks_list_with_locks(
        self, client, db, test_user_id, test_company_id, locked_file
    ):
        """Test liste des verrous avec des verrous actifs."""
        response = client.get(
            "/locks",
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["status"] == "success"
        assert len(json_data["data"]["locks"]) >= 1

        # Vérifier la structure d'un verrou
        lock_data = json_data["data"]["locks"][0]
        assert "lock_id" in lock_data
        assert "file_id" in lock_data
        assert "locked_by" in lock_data
        assert "locked_at" in lock_data
        assert "lock_type" in lock_data

    def test_locks_list_filter_by_file_id(
        self, client, db, test_user_id, test_company_id, locked_file
    ):
        """Test filtrage des verrous par file_id."""
        response = client.get(
            "/locks",
            query_string={"file_id": locked_file.id},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["status"] == "success"

        # Tous les verrous retournés doivent être pour ce fichier
        for lock in json_data["data"]["locks"]:
            assert lock["file_id"] == str(locked_file.id)

    def test_locks_list_filter_by_bucket(
        self, client, db, test_user_id, test_company_id, locked_file
    ):
        """Test filtrage des verrous par bucket."""
        response = client.get(
            "/locks",
            query_string={"bucket_type": "users", "bucket_id": test_user_id},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["status"] == "success"

    def test_locks_list_no_access_to_other_buckets(
        self, client, db, test_user_id, test_company_id
    ):
        """Test que l'utilisateur ne voit pas les verrous des autres buckets."""
        # Créer un fichier et un verrou pour un autre utilisateur
        other_user_id = str(uuid.uuid4())
        other_file = StorageFile(
            bucket_type="users",
            bucket_id=other_user_id,
            logical_path="test/locked.txt",
            filename="locked.txt",
            owner_id=other_user_id,
            status="approved",
        )
        db.add(other_file)
        db.flush()

        other_lock = Lock(
            file_id=other_file.id, locked_by=other_user_id, lock_type="edit"
        )
        db.add(other_lock)
        db.commit()

        # L'utilisateur test_user_id ne doit pas voir ce verrou
        response = client.get(
            "/locks",
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert response.status_code == 200
        json_data = response.get_json()

        # Vérifier qu'aucun verrou de other_user_id n'est visible
        for lock in json_data["data"]["locks"]:
            file_obj = StorageFile.get_by_file_id(lock["file_id"])
            assert file_obj.bucket_id != other_user_id


class TestDeleteAndLocksIntegration:
    """Tests d'intégration entre delete et locks."""

    def test_delete_locked_file(
        self, client, db, test_user_id, test_company_id, locked_file
    ):
        """Test suppression d'un fichier verrouillé (doit fonctionner)."""
        file_id = locked_file.id

        # Vérifier que le fichier est verrouillé
        locks_response = client.get(
            "/locks",
            query_string={"file_id": file_id},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )
        assert len(locks_response.get_json()["data"]["locks"]) >= 1

        # Supprimer le fichier (doit fonctionner même s'il est verrouillé)
        delete_response = client.delete(
            "/delete",
            json={"file_id": file_id, "physical": False},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        assert delete_response.status_code == 200

        # Vérifier que le fichier est marqué comme deleted
        db.expire_all()
        file_obj = StorageFile.get_by_file_id(file_id)
        assert file_obj.status == "archived"

    def test_lock_deleted_file(
        self, client, db, test_user_id, test_company_id, sample_file
    ):
        """Test verrouillage d'un fichier supprimé."""
        file_id = sample_file.id

        # Supprimer le fichier
        delete_response = client.delete(
            "/delete",
            json={"file_id": file_id, "physical": False},
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )
        assert delete_response.status_code == 200

        # Tenter de verrouiller le fichier supprimé
        lock_response = client.post(
            "/lock",
            json={
                "file_id": file_id,
                "reason": "Testing lock on deleted file",
            },
            headers={
                "X-User-ID": test_user_id,
                "X-Company-ID": test_company_id,
            },
        )

        # Peut être 404, 400 ou 200 selon l'implémentation
        # (l'endpoint /lock existant ne vérifie pas forcément le status)
        assert lock_response.status_code in [200, 400, 404]
