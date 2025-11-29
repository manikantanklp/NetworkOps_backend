from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime
from pathlib import Path

# ---- Old APIs (Inventory / Discovery / Config Push) ----
from inventory import (
    load_inventory,
    add_device_to_inventory,
    delete_device_from_inventory,
)
from discovery_handler import run_discovery_api
from status_checker import get_device_status
from config_push import push_config

# ---- NOC Dashboard Logic ----
from utils.health import compute_health_overview, compute_device_health_score
from utils.compliance import evaluate_compliance_overview
from utils.diff import get_before_after_for_device, compute_diff_summary
from utils.insights import generate_recommendations

# ---------------------------------
# App Setup
# ---------------------------------

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Helper to load JSON
def load_json(fname: str):
    with open(DATA_DIR / fname, "r") as f:
        return json.load(f)

# Load NOC mock data
DEVICES = load_json("devices.json")
LINKS = load_json("links.json")
AUTOMATION = load_json("automation.json")
BACKUPS = load_json("backups.json")
COMPLIANCE = load_json("compliance.json")
ALERTS = load_json("alerts.json")
TRENDS = load_json("trends.json")

# =========================================================
#  OLD BACKEND APIs
# =========================================================
# --------------------------
# RUN SINGLE SSH COMMAND
# --------------------------
from netmiko import ConnectHandler

@app.route("/api/run-command", methods=["POST"])
def api_run_command():
    data = request.json

    ip = data.get("ip")
    username = data.get("username")
    password = data.get("password")
    command = data.get("command")

    # Validation
    if not ip:
        return jsonify({"error": "IP required"}), 400
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if not command:
        return jsonify({"error": "command required"}), 400

    try:
        device = {
            "device_type": "cisco_ios",
            "host": ip,
            "username": username,
            "password": password
        }

        ssh = ConnectHandler(**device)
        ssh.enable()

        output = ssh.send_command(command)
        ssh.disconnect()

        return jsonify({
            "success": True,
            "output": output
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/inventory", methods=["GET"])
def api_inventory():
    return jsonify(load_inventory())


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(get_device_status("network_inventory.json"))


@app.route("/api/discover", methods=["POST"])
def api_discover():
    data = request.json
    start_ip = data.get("start_ip")

    if not start_ip:
        return jsonify({"success": False, "error": "start_ip required"}), 400
    
    try:
        result = run_discovery_api(start_ip)

        return jsonify({
            "success": True,
            "devices_found": result.get("total_devices", 0),
            "new_devices": result.get("new_devices", []),
            "inventory": result.get("all_devices", []),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/device", methods=["POST"])
def api_add_device():
    data = request.json
    ip = data.get("ip")

    if not ip:
        return jsonify({"error": "IP required"}), 400

    result = add_device_to_inventory(
        ip,
        data.get("hostname", "unknown"),
        data.get("username", "netkode"),
        data.get("password", "netkode")
    )

    return jsonify(result)


@app.route("/api/device/<ip>", methods=["DELETE"])
def api_delete_device(ip):
    return jsonify(delete_device_from_inventory(ip))


@app.route("/api/config", methods=["POST"])
def api_push_config():
    data = request.json

    ip = data.get("ip")
    raw_config = data.get("config")
    commands = data.get("commands")

    if not ip:
        return jsonify({"error": "IP required"}), 400
    
    # Convert textarea → commands list
    if raw_config:
        commands = [line.strip() for line in raw_config.split("\n") if line.strip()]

    if not commands:
        return jsonify({"error": "No commands provided"}), 400

    # Find credentials from inventory
    devices = load_inventory()
    dev = next((d for d in devices if d["ip"] == ip), None)

    if not dev:
        return jsonify({"error": "Device not found"}), 404

    result = push_config(
        ip=ip,
        username=dev.get("username"),
        password=dev.get("password"),
        commands=commands
    )

    return jsonify(result)

# =========================================================
#  NOC / DASHBOARD APIS
# =========================================================

@app.route("/api/devices", methods=["GET"])
def api_devices():
    return jsonify({"devices": DEVICES})


@app.route("/api/health", methods=["GET"])
def api_health():
    overview = compute_health_overview(DEVICES)
    
    devices_health = []
    for d in DEVICES:
        dd = d.copy()
        dd["computedHealth"] = compute_device_health_score(d)
        devices_health.append(dd)

    return jsonify({"overview": overview, "devices": devices_health})


@app.route("/api/automation/summary", methods=["GET"])
def api_automation_summary():

    total = len(AUTOMATION)
    success = sum(1 for t in AUTOMATION if t["status"] == "success")

    by_type = {}
    for t in AUTOMATION:
        by_type[t["taskType"]] = by_type.get(t["taskType"], 0) + 1

    recent = sorted(AUTOMATION, key=lambda x: x["startedAt"], reverse=True)[:10]

    return jsonify({
        "total": total,
        "success": success,
        "failed": total - success,
        "byType": by_type,
        "recent": recent
    })


@app.route("/api/config/<device_id>", methods=["GET"])
def api_config_diff(device_id):
    r = get_before_after_for_device(device_id, BACKUPS)
    if not r:
        return jsonify({"error": "Device or backups not found"}), 404
    
    before, after = r
    diff_summary = compute_diff_summary(before, after)

    return jsonify({
        "deviceId": device_id,
        "before": before,
        "after": after,
        "diffSummary": diff_summary
    })


@app.route("/api/compliance", methods=["GET"])
def api_compliance():
    return jsonify(evaluate_compliance_overview(DEVICES, COMPLIANCE))


@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    total = len(ALERTS)
    open_count = sum(1 for a in ALERTS if a["status"] == "open")
    by_severity = {}

    for a in ALERTS:
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1

    recent = sorted(ALERTS, key=lambda x: x["openedAt"], reverse=True)[:20]

    return jsonify({
        "total": total,
        "open": open_count,
        "closed": total - open_count,
        "bySeverity": by_severity,
        "recent": recent
    })


@app.route("/api/trends", methods=["GET"])
def api_trends():
    try:
        range_val = int(request.args.get("range", 7))
    except ValueError:
        return jsonify({"error": "Invalid range"}), 400

    if range_val not in [7, 30]:
        return jsonify({"error": "Use range=7 or range=30"}), 400

    return jsonify({
        "range": range_val,
        "data": TRENDS.get(f"{range_val}d", [])
    })


@app.route("/api/recommendations", methods=["GET"])
def api_recommendations():
    return jsonify({
        "insights": generate_recommendations(
            DEVICES, ALERTS, AUTOMATION, COMPLIANCE
        )
    })


@app.route("/api/topology", methods=["GET"])
def api_topology():
    return jsonify({"devices": DEVICES, "links": LINKS})


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
