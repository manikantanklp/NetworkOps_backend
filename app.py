from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")


# ---- Old APIs (inventory / discovery / config push) ----
from inventory import (
    load_inventory,
    add_device_to_inventory,
    delete_device_from_inventory,
)
from discovery_handler import run_discovery_api
from status_checker import get_device_status
from config_push import push_config
from servicenow_api import get_incidents 

# ---- NOC Dashboard Utils ----
from utils.health import compute_health_overview, compute_device_health_score
from utils.compliance import evaluate_compliance_overview
from utils.diff import get_before_after_for_device, compute_diff_summary
from utils.insights import generate_recommendations

# ---------------------------------
# App Setup
# ---------------------------------

app = Flask(__name__)
CORS(app)  # allow all origins (for React frontend, etc.)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# ---------------------------------
# Helpers
# ---------------------------------

def load_json(fname: str):
    path = DATA_DIR / fname
    with open(path, "r") as f:
        return json.load(f)

# ---------------------------------
# Load Mock DB into Memory (NOC data)
# ---------------------------------

DEVICES = load_json("devices.json")
LINKS = load_json("links.json")
AUTOMATION = load_json("automation.json")
BACKUPS = load_json("backups.json")
COMPLIANCE = load_json("compliance.json")
ALERTS = load_json("alerts.json")
TRENDS = load_json("trends.json")

# =========================================================
#  OLD BACKEND APIs (Network Discovery / Inventory / Config)
# =========================================================

# --------------------------
# GET INVENTORY
# --------------------------
@app.route("/api/inventory", methods=["GET"])
def api_inventory():
    return jsonify(load_inventory())


# --------------------------
# GET STATUS OF DEVICES
# --------------------------
@app.route("/api/status", methods=["GET"])
def api_status():
    # network_inventory.json path/format same as before
    return jsonify(get_device_status("network_inventory.json"))


# --------------------------
# RUN NETWORK DISCOVERY
# --------------------------
@app.route("/api/discover", methods=["POST"])
def api_discover():
    data = request.json
    start_ip = data.get("start_ip")

    if not start_ip:
        return jsonify({"success": False, "error": "start_ip required"}), 400

    try:
        result = run_discovery_api(start_ip)

        # Normalize keys for React
        response = {
            "success": True,
            "devices_found": result.get("total_devices", 0),
            "new_devices": result.get("new_devices", []),
            "inventory": result.get("all_devices", []),
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------------------------
# ADD DEVICE TO INVENTORY
# --------------------------
@app.route("/api/device", methods=["POST"])
def api_add_device():
    data = request.json

    ip = data.get("ip")
    hostname = data.get("hostname", "unknown")
    username = data.get("username", "netkode")
    password = data.get("password", "netkode")

    if not ip:
        return jsonify({"error": "IP required"}), 400

    result = add_device_to_inventory(ip, hostname, username, password)
    return jsonify(result)


# --------------------------
# DELETE DEVICE FROM INVENTORY
# --------------------------
@app.route("/api/device/<ip>", methods=["DELETE"])
def api_delete_device(ip):
    result = delete_device_from_inventory(ip)
    return jsonify(result)


# --------------------------
# PUSH CONFIG TO DEVICE
# --------------------------
@app.route("/api/config", methods=["POST"])
def api_push_config():
    """
    Push config commands to a device.
    NOTE: This is POST /api/config (different from GET /api/config/<device_id> below).
    """
    data = request.json

    ip = data.get("ip")
    commands = data.get("commands")

    if not ip or not commands:
        return jsonify({"error": "ip and commands required"}), 400

    # Fetch credentials from inventory
    devices = load_inventory()
    dev = next((d for d in devices if d["ip"] == ip), None)

    if not dev:
        return jsonify({"error": "Device not found in inventory"}), 404

    result = push_config(
        ip=ip,
        username=dev.get("username"),
        password=dev.get("password"),
        commands=commands,
    )

    return jsonify(result)


# =========================================================
#  NOC DASHBOARD APIs (LAN Automation / Monitoring)
# =========================================================

# -------------------------------
# Device Inventory Summary
# -------------------------------
@app.route("/api/devices", methods=["GET"])
def api_devices():
    return jsonify({"devices": DEVICES})


# -------------------------------
# Device Health Stats
# -------------------------------
@app.route("/api/health", methods=["GET"])
def api_health():
    overview = compute_health_overview(DEVICES)

    devices_health = []
    for d in DEVICES:
        health_score = compute_device_health_score(d)
        dd = d.copy()
        dd["computedHealth"] = health_score
        devices_health.append(dd)

    return jsonify({
        "overview": overview,
        "devices": devices_health
    })


# -------------------------------
# Automation Task Summary
# -------------------------------
@app.route("/api/automation/summary", methods=["GET"])
def api_automation_summary():
    total = len(AUTOMATION)
    success = sum(1 for t in AUTOMATION if t["status"] == "success")
    failed = total - success

    by_type = {}
    for t in AUTOMATION:
        ttype = t["taskType"]
        by_type[ttype] = by_type.get(ttype, 0) + 1

    recent = sorted(
        AUTOMATION,
        key=lambda x: x["startedAt"],
        reverse=True
    )[:10]

    return jsonify({
        "total": total,
        "success": success,
        "failed": failed,
        "byType": by_type,
        "recent": recent
    })


# -------------------------------
# Before / After Config Backup Diff
# -------------------------------
@app.route("/api/config/<device_id>", methods=["GET"])
def api_config_diff(device_id):
    """
    Returns before/after backups + diffSummary for a device.
    (This is GET /api/config/<device_id>, different from POST /api/config above.)
    """
    result = get_before_after_for_device(device_id, BACKUPS)

    if not result:
        return jsonify({"error": "Device or backups not found"}), 404

    before, after = result
    diff_summary = compute_diff_summary(before, after)

    return jsonify({
        "deviceId": device_id,
        "before": before,
        "after": after,
        "diffSummary": diff_summary
    })


# -------------------------------
# Compliance Overview
# -------------------------------
@app.route("/api/compliance", methods=["GET"])
def api_compliance():
    overview = evaluate_compliance_overview(DEVICES, COMPLIANCE)
    return jsonify(overview)


# -------------------------------
# Alerts / Incidents
# -------------------------------
@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    total = len(ALERTS)
    open_count = sum(1 for a in ALERTS if a["status"] == "open")
    closed_count = total - open_count

    by_severity = {}
    for a in ALERTS:
        sev = a["severity"]
        by_severity[sev] = by_severity.get(sev, 0) + 1

    recent = sorted(
        ALERTS,
        key=lambda x: x["openedAt"],
        reverse=True
    )[:20]

    return jsonify({
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "bySeverity": by_severity,
        "recent": recent
    })


# -------------------------------
# Trends (7d / 30d)
# -------------------------------
@app.route("/api/trends", methods=["GET"])
def api_trends():
    """
    Trends: ?range=7 or ?range=30
    """
    try:
        range_val = int(request.args.get("range", 7))
    except ValueError:
        return jsonify({"error": "Invalid range"}), 400

    if range_val == 7:
        data = TRENDS.get("7d", [])
    elif range_val == 30:
        data = TRENDS.get("30d", [])
    else:
        return jsonify({"error": "Unsupported range. Use 7 or 30."}), 400

    return jsonify({
        "range": range_val,
        "data": data
    })


# -------------------------------
# Recommendations / Insights
# -------------------------------
@app.route("/api/recommendations", methods=["GET"])
def api_recommendations():
    insights = generate_recommendations(
        DEVICES,
        ALERTS,
        AUTOMATION,
        COMPLIANCE
    )

    return jsonify({"insights": insights})


# -------------------------------
# Topology (optional helper if needed)
# -------------------------------
@app.route("/api/topology", methods=["GET"])
def api_topology():
    """
    Simple topology: devices + links for frontend graph.
    """
    return jsonify({
        "devices": DEVICES,
        "links": LINKS
    })

# ===============================
# 🎫 Ticketing Dashboard API
# ===============================

@app.route("/api/tickets", methods=["GET"])
def api_tickets():
    try:
        tickets = get_incidents()  # Fetch live from ServiceNow
        return jsonify(tickets)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tickets/count", methods=["GET"])
def api_tickets_count():
    try:
        tickets = get_incidents()  # get from ServiceNow
        return jsonify({"count": len(tickets)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Health Check
# -------------------------------
@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "ok",
        "time": datetime.utcnow().isoformat()
    })


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    # Single server that serves BOTH old and new APIs
    app.run(host="0.0.0.0", port=8000, debug=True)
    # kkjbjb