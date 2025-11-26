import json
from netmiko import ConnectHandler

INVENTORY_FILE = "network_inventory.json"

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            data = f.read().strip()

            # If file is empty, return empty list
            if not data:
                return []

            return json.loads(data)

    except FileNotFoundError:
        # If file doesn’t exist, create it and return empty list
        save_inventory([])
        return []

    except json.JSONDecodeError:
        # File corrupted → reset
        save_inventory([])
        return []


def save_inventory(devices):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(devices, f, indent=4)


def add_device_to_inventory(ip, hostname, username, password):
    devices = load_inventory()
    
    # Check duplicates
    for d in devices:
        if d.get("ip") == ip:
            return {"error": "Device already exists"}

    devices.append({
        "ip": ip,
        "hostname": hostname,
        "username": username,
        "password": password
    })

    save_inventory(devices)
    return {"message": "Device added", "count": len(devices)}


def delete_device_from_inventory(ip):
    devices = load_inventory()
    new_list = [d for d in devices if d.get("ip") != ip]

    if len(devices) == len(new_list):
        return {"error": "Device not found"}

    save_inventory(new_list)
    return {"message": f"Device {ip} deleted", "count": len(new_list)}
