from netmiko import ConnectHandler
import re
import json

# Globals
visited = set()
device_inventory = {}  # hostname → device object

USERNAME = "netkode"
PASSWORD = "netkode"


def connect(ip):
    """Connect to device via SSH."""
    try:
        device = {
            "device_type": "autodetect",
            "host": ip,
            "username": USERNAME,
            "password": PASSWORD,
            "timeout": 5,
        }
        conn = ConnectHandler(**device)
        conn.enable()
        return conn
    except Exception as e:
        print(f"[ERROR] Connection failed for {ip}: {e}")
        return None


def get_vendor(output):
    """Determine vendor from 'show version' output."""
    output = output.lower()
    if "cisco ios" in output:
        return "Cisco"
    elif "junos" in output:
        return "Juniper"
    elif "arista" in output:
        return "Arista"
    return "Unknown"


def parse_neighbors(output):
    """Parse CDP neighbors."""
    neighbors = []
    sections = output.split("Device ID:")
    for sec in sections[1:]:
        nb = {}
        lines = sec.strip().splitlines()
        nb["hostname"] = lines[0].strip()
        ip_match = re.search(r"IP address: (\S+)", sec)
        nb["ip"] = ip_match.group(1) if ip_match else None
        neighbors.append(nb)
    return neighbors


def collect_info(conn, ip):
    """Collect hostname, vendor, and neighbors from a device."""
    info = {"ip": ip}

    try:
        hostname = conn.send_command("show run | include hostname").strip()
        info["hostname"] = hostname.replace("hostname ", "") if hostname else ip
    except:
        info["hostname"] = ip

    try:
        ver = conn.send_command("show version")
        info["vendor"] = get_vendor(ver)
    except:
        info["vendor"] = "Unknown"

    try:
        cdp = conn.send_command("show cdp neighbors detail")
        info["neighbors"] = parse_neighbors(cdp)
    except:
        info["neighbors"] = []

    return info


def update_inventory(info):
    """Add or update device info in the inventory."""
    hostname = info["hostname"]

    if hostname not in device_inventory:
        device_inventory[hostname] = {
            "hostname": hostname,
            "vendor": info.get("vendor", "Unknown"),
            "interfaces": [info.get("ip")] if info.get("ip") else [],
            "neighbors": [nb["hostname"] for nb in info.get("neighbors", [])],
            "username": USERNAME,
            "password": PASSWORD
        }
    else:
        ip = info.get("ip")
        if ip and ip not in device_inventory[hostname]["interfaces"]:
            device_inventory[hostname]["interfaces"].append(ip)

        for nb in info.get("neighbors", []):
            if nb["hostname"] not in device_inventory[hostname]["neighbors"]:
                device_inventory[hostname]["neighbors"].append(nb["hostname"])


def discover(ip):
    """Recursive device discovery."""
    if ip in visited:
        return
    visited.add(ip)

    print(f"\n[SCAN] {ip}")
    conn = connect(ip)
    if conn is None:
        return

    info = collect_info(conn, ip)
    update_inventory(info)

    hostname = info["hostname"]
    print(f"[DISCOVERED] {hostname} - IPs: {device_inventory[hostname]['interfaces']}")
    print(" → Neighbors:")
    for nb in info["neighbors"]:
        print(f"    {nb['hostname']} ({nb['ip']})")

    # Discover neighbors recursively
    for nb in info["neighbors"]:
        if nb["ip"]:
            discover(nb["ip"])

    conn.disconnect()


def run_discovery_api(start_ip):
    """API-style function for discovery and JSON export."""
    global visited, device_inventory
    visited = set()
    device_inventory = {}

    try:
        discover(start_ip)

        # Save inventory to JSON
        final_list = list(device_inventory.values())
        with open("network_inventory.json", "w") as f:
            json.dump(final_list, f, indent=4)

        return {
            "status": "success",
            "total_devices": len(final_list),
            "all_devices": final_list
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    START_IP = "192.168.1.1"
    result = run_discovery_api(START_IP)
    print(json.dumps(result, indent=4))
