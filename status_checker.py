import json
import subprocess

def ping_ip(ip, count=1, timeout=1):
    """Ping single IP from host system"""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except:
        return False


def get_device_status(inventory_file):
    with open(inventory_file, "r") as f:
        devices = json.load(f)

    status_result = {}

    for device in devices:
        hostname = device.get("hostname")
        interfaces = device.get("interfaces", [])

        device_status = "OFF"

        # ping every interface IP of the device
        for ip in interfaces:
            if ping_ip(ip):
                device_status = "ON"
                break   # no need to check other interfaces

        status_result[hostname] = device_status

    return status_result


if __name__ == "__main__":
    print(get_device_status("network_inventory.json"))
