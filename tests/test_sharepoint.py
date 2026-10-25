import hashlib
import json
from pathlib import Path

import pytest

from andinos_etl import sharepoint
from andinos_etl.sharepoint import ConfiguracionSharePoint, ErrorPublicacionSharePoint, publicar_artifact


def _artifact(tmp_path: Path, estado: str = "APPROVED") -> Path:
    artifact = tmp_path / "approved"
    artifact.mkdir()
    (artifact / "modelo_estrella.xlsx").write_bytes(b"modelo")
    (artifact / "gate.json").write_text(json.dumps({"status": estado}), encoding="utf-8")
    (artifact / "manifest.json").write_text(json.dumps({"git_commit": "abc123"}), encoding="utf-8")
    (artifact / "checksums.sha256").write_text("hash  modelo_estrella.xlsx\n", encoding="utf-8")
    return artifact


def _configuracion() -> ConfiguracionSharePoint:
    return ConfiguracionSharePoint(
        site_id="site",
        folder="modelo-andinos",
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
    )


def test_no_publica_si_gate_no_esta_aprobado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact(tmp_path, "REJECTED")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    with pytest.raises(ErrorPublicacionSharePoint, match="APPROVED"):
        publicar_artifact(artifact, _configuracion(), token="token")


def test_no_publica_si_commit_no_corresponde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "otro-commit")

    with pytest.raises(ErrorPublicacionSharePoint, match="commit"):
        publicar_artifact(artifact, _configuracion(), token="token")


def test_publica_payload_primero_y_checksum_ultimo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    subidos: list[str] = []
    hashes: dict[str, str] = {}

    monkeypatch.setattr(sharepoint, "_asegurar_carpeta", lambda *args: {})
    def subir(*args) -> None:
        archivo = args[3]
        subidos.append(archivo.name)
        hashes[archivo.name] = hashlib.sha256(archivo.read_bytes()).hexdigest()

    def hash_remoto(*args) -> str:
        return hashes[args[3].name]

    monkeypatch.setattr(sharepoint, "_subir_archivo", subir)
    monkeypatch.setattr(sharepoint, "_hash_remoto", hash_remoto)

    resultado = publicar_artifact(artifact, _configuracion(), token="token")

    assert resultado["status"] == "PUBLISHED"
    assert subidos[-1] == "checksums.sha256"
    assert subidos[-2] == "manifest.json"
    assert subidos.index("modelo_estrella.xlsx") < subidos.index("manifest.json")


def test_asegura_carpeta_anidada_creando_cada_nivel(monkeypatch: pytest.MonkeyPatch) -> None:
    creados: list[tuple[str, str, str]] = []

    def pedir_json(metodo: str, url: str, token: str, cuerpo: dict | None = None) -> dict:
        if metodo == "POST":
            item_id = f"item-{len(creados) + 1}"
            creados.append((cuerpo["name"], item_id, url))
            return {"id": item_id}
        return {"id": "root"}

    def item_carpeta(*args) -> dict:
        raise ErrorPublicacionSharePoint("Microsoft Graph respondió 404: no existe")

    monkeypatch.setattr(sharepoint, "_pedir_json", pedir_json)
    monkeypatch.setattr(sharepoint, "_item_carpeta", item_carpeta)

    resultado = sharepoint._asegurar_carpeta(_configuracion(), "token", "modelo-andinos/run-123-attempt-1")

    assert [(nombre, item_id) for nombre, item_id, _ in creados] == [
        ("modelo-andinos", "item-1"),
        ("run-123-attempt-1", "item-2"),
    ]
    assert "/drive/items/root/children" in creados[0][2]
    assert "/drive/items/item-1/children" in creados[1][2]
    assert resultado["id"] == "item-2"
