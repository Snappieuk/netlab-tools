#!/usr/bin/env python3

from flask import Flask

from app.models import db
from app.routes.netlabs import netlabs_api_bp
from app.services.netlabs_service import infer_room, list_room_machines, upsert_machine_heartbeat


def _make_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True
    db.init_app(app)
    app.register_blueprint(netlabs_api_bp)
    return app


def test_room_inference_and_room_listing():
    app = _make_app()
    with app.app_context():
        db.create_all()
        upsert_machine_heartbeat({"hostname": "room12-pc01", "ip": "10.0.0.10"})
        room = infer_room("room12-pc01")
        assert room == "Room 12"
        room_machines = list_room_machines("Room 12")
        assert len(room_machines) == 1
        assert room_machines[0]["hostname"] == "room12-pc01"


def test_heartbeat_and_rdp_endpoint():
    app = _make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    heartbeat = client.post("/api/heartbeat", json={"hostname": "rm5-win01", "ip": "10.0.0.22"})
    assert heartbeat.status_code == 200
    payload = heartbeat.get_json()
    assert payload["ok"] is True
    assert payload["machine"]["room"] == "Room 5"

    rdp = client.get("/rdp/rm5-win01.rdp")
    assert rdp.status_code == 200
    assert "application/x-rdp" in (rdp.content_type or "")
    assert "full address:s:10.0.0.22:3389" in rdp.get_data(as_text=True)
