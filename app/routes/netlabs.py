#!/usr/bin/env python3
"""
Netlabs dashboard and heartbeat routes.
"""

from flask import Blueprint, Response, jsonify, render_template, request

from app.models import NetlabMachine
from app.services.netlabs_service import (
    build_machine_rdp_content,
    list_machines,
    list_room_machines,
    list_rooms,
    upsert_machine_heartbeat,
)
from app.utils.decorators import login_required

netlabs_bp = Blueprint("netlabs", __name__, url_prefix="/netlabs")
netlabs_api_bp = Blueprint("netlabs_api", __name__)


@netlabs_bp.route("")
@login_required
def dashboard():
    """Room and machine overview."""
    return render_template(
        "netlabs/dashboard.html",
        rooms=list_rooms(),
        machines=list_machines(),
    )


@netlabs_bp.route("/rooms/<room>")
@login_required
def room_detail(room: str):
    """Single-room machine detail page."""
    return render_template(
        "netlabs/room.html",
        room=room,
        machines=list_room_machines(room),
    )


@netlabs_api_bp.route("/api/heartbeat", methods=["POST"])
@netlabs_api_bp.route("/api/netlabs/heartbeat", methods=["POST"])
def heartbeat():
    """Heartbeat ingestion endpoint for netlabs agents."""
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        machine = upsert_machine_heartbeat(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "machine": machine.to_dict()})


@netlabs_api_bp.route("/rdp/<hostname>.rdp")
@netlabs_api_bp.route("/netlabs/rdp/<hostname>.rdp")
def netlabs_rdp(hostname: str):
    """RDP download by netlabs hostname."""
    machine = NetlabMachine.query.filter_by(hostname=hostname.lower()).first()
    if not machine:
        return jsonify({"ok": False, "error": "Machine not found"}), 404

    content = build_machine_rdp_content(machine)
    response = Response(content, mimetype="application/x-rdp")
    response.headers["Content-Disposition"] = f'attachment; filename="{machine.hostname}.rdp"'
    return response
