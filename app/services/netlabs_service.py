#!/usr/bin/env python3
"""
Netlabs machine heartbeat and room dashboard service.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models import NetlabMachine, db

STALE_AFTER_SECONDS = 120
OFFLINE_AFTER_SECONDS = 600


def infer_room(hostname: str) -> str:
    """Infer room name from hostname using lightweight heuristics."""
    if not hostname:
        return "Unknown"

    match = re.search(r"(?:room|rm)?([a-z]?\d{1,3})", hostname.lower())
    if match:
        room_token = match.group(1).upper()
        return f"Room {room_token}"

    for splitter in ("-", "_", "."):
        if splitter in hostname:
            token = hostname.split(splitter)[0].strip()
            return token.upper() if token else "Unknown"

    return "Unknown"


def machine_status(last_seen: Optional[datetime], now: Optional[datetime] = None) -> str:
    """Get machine state from heartbeat age."""
    if not last_seen:
        return "offline"

    now = now or datetime.utcnow()
    age = now - last_seen
    if age <= timedelta(seconds=STALE_AFTER_SECONDS):
        return "online"
    if age <= timedelta(seconds=OFFLINE_AFTER_SECONDS):
        return "stale"
    return "offline"


def upsert_machine_heartbeat(payload: Dict[str, Any]) -> NetlabMachine:
    """Create/update machine from heartbeat payload."""
    hostname = (payload.get("hostname") or payload.get("machine") or "").strip().lower()
    if not hostname:
        raise ValueError("Heartbeat payload must include hostname")

    machine = NetlabMachine.query.filter_by(hostname=hostname).first()
    if not machine:
        machine = NetlabMachine(hostname=hostname)
        db.session.add(machine)

    machine.ip_address = payload.get("ip_address") or payload.get("ip") or machine.ip_address
    machine.display_name = payload.get("display_name") or payload.get("name") or machine.display_name
    machine.agent_version = payload.get("agent_version") or machine.agent_version
    machine.room = (payload.get("room") or infer_room(hostname) or "Unknown").strip()[:64]
    machine.last_seen = datetime.utcnow()

    db.session.commit()
    return machine


def list_machines() -> List[Dict[str, Any]]:
    """List all machines sorted for dashboard display."""
    now = datetime.utcnow()
    machines = NetlabMachine.query.order_by(NetlabMachine.room.asc(), NetlabMachine.hostname.asc()).all()
    results = []
    for machine in machines:
        machine_data = machine.to_dict()
        machine_data["status"] = machine_status(machine.last_seen, now=now)
        results.append(machine_data)
    return results


def list_rooms() -> List[Dict[str, Any]]:
    """Aggregate room overview with basic status counts."""
    summary: Dict[str, Dict[str, Any]] = {}
    for machine in list_machines():
        room = machine["room"] or "Unknown"
        if room not in summary:
            summary[room] = {
                "room": room,
                "machine_count": 0,
                "online": 0,
                "stale": 0,
                "offline": 0,
            }
        summary[room]["machine_count"] += 1
        summary[room][machine["status"]] += 1

    return sorted(summary.values(), key=lambda entry: entry["room"])


def list_room_machines(room: str) -> List[Dict[str, Any]]:
    """Return machine list for a single room."""
    normalized = room.strip().lower()
    return [m for m in list_machines() if (m.get("room") or "").lower() == normalized]


def build_machine_rdp_content(machine: NetlabMachine) -> str:
    """Build minimal RDP file content from machine heartbeat state."""
    address = machine.ip_address or machine.hostname
    return (
        f"full address:s:{address}:3389\r\n"
        "prompt for credentials:i:1\r\n"
        "authentication level:i:2\r\n"
        "screen mode id:i:2\r\n"
        "desktopwidth:i:1920\r\n"
        "desktopheight:i:1080\r\n"
        "session bpp:i:32\r\n"
        "redirectclipboard:i:1\r\n"
        "autoreconnection enabled:i:1\r\n"
    )
