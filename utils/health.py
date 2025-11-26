# real-appli-back/utils/health.py
from typing import List, Dict
import math

def compute_device_health_score(device: Dict) -> int:
    """
    Recompute a derived health score from CPU/memory/alerts/warnings.
    Returns integer 0-100.
    """
    cpu = device.get("cpuUsage", 0)
    mem = device.get("memoryUsage", 0)
    base = device.get("healthScore", 80)
    # penalize high cpu/memory
    penalty = 0
    if cpu > 80:
        penalty += (cpu - 80) * 0.6
    elif cpu > 60:
        penalty += (cpu - 60) * 0.3
    if mem > 80:
        penalty += (mem - 80) * 0.4
    # warnings reduce score slightly
    warnings = device.get("warnings", 0)
    critical = device.get("criticalAlerts", 0)
    penalty += warnings * 1.5 + critical * 5
    score = max(10, int(round(base - penalty)))
    return min(100, score)

def compute_health_overview(devices: List[Dict]) -> Dict:
    """
    Aggregate overview: averages grouped by layer / role
    """
    groups = {}
    for d in devices:
        key = d.get("layer", "unknown")
        if key not in groups:
            groups[key] = {"count":0,"avgCpu":0,"avgMem":0,"avgHealth":0}
        g = groups[key]
        g["count"] += 1
        g["avgCpu"] += d.get("cpuUsage",0)
        g["avgMem"] += d.get("memoryUsage",0)
        g["avgHealth"] += compute_device_health_score(d)
    # finalize averages
    for k,v in groups.items():
        if v["count"]>0:
            v["avgCpu"] = int(round(v["avgCpu"]/v["count"]))
            v["avgMem"] = int(round(v["avgMem"]/v["count"]))
            v["avgHealth"] = int(round(v["avgHealth"]/v["count"]))
    # overall
    overall = {
        "byLayer": groups,
        "totalDevices": len(devices),
        "avgHealthAll": int(round(sum(compute_device_health_score(d) for d in devices)/len(devices)))
    }
    return overall
