from fastapi.testclient import TestClient


def test_app_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "18099")
    monkeypatch.delenv("MQTT_HOST", raising=False)
    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        created = client.post(
            "/api/scenes", json={"name": "Tudo apagado", "scene_number": 0, "enabled": True}
        )
        assert created.status_code == 201
        scene = created.json()
        assert client.get("/api/scenes").json()[0]["scene_number"] == 0
        sent = client.post(f"/api/scenes/{scene['id']}/test")
        assert sent.status_code == 200
        assert sent.json()["packet"]["payload_hex"] == "02 00 00 FF"
        lab = client.post("/api/settings/protocol-lab", json={"enabled": True, "confirmed": True})
        assert lab.status_code == 200
        diagnostics = client.get("/api/diagnostics")
        assert diagnostics.status_code == 200
        assert diagnostics.json()["settings"]["udp_port"] == 8760

