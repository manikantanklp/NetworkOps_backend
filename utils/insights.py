# real-appli-back/utils/insights.py
from typing import List, Dict
from collections import Counter

def generate_recommendations(devices: List[Dict], alerts: List[Dict], automation: List[Dict], compliance_data: Dict) -> Dict:
    """
    Generate human-readable recommendations based on current system state.
    """
    recs = {"performance": [], "reliability": [], "compliance": [], "automation": []}
    # High CPU devices
    high_cpu = [d for d in devices if d.get("cpuUsage",0) >= 70]
    if high_cpu:
        recs["performance"].append(f"High CPU devices: {', '.join(d['name'] for d in high_cpu)}. Consider traffic shaping or capacity review.")
    else:
        recs["performance"].append("No devices currently with sustained high CPU.")

    # Devices with low health
    low_health = [d for d in devices if d.get("healthScore", 100) < 80]
    if low_health:
        recs["reliability"].append(f"Devices with health < 80: {', '.join(d['name'] for d in low_health)}. Investigate warnings/alerts.")
    else:
        recs["reliability"].append("All devices maintain acceptable health scores.")

    # Repeated alerts
    device_alert_counts = Counter(a["deviceId"] for a in alerts)
    repeated = [dev for dev,count in device_alert_counts.items() if count >= 2]
    if repeated:
        recs["reliability"].append(f"Devices with repeated alerts: {', '.join(repeated)}. Root cause investigation recommended.")
    # Compliance
    comp_summary = evaluate_simple_compliance_summary(devices, compliance_data)
    if comp_summary["nonCompliant"]:
        recs["compliance"].append(f"Non-compliant devices: {', '.join(comp_summary['nonCompliantList'])}. Schedule remediation.")
    else:
        recs["compliance"].append("All devices compliant with baseline rules.")

    # Automation suggestions
    failed_tasks = [t for t in automation if t["status"] != "success"]
    if failed_tasks:
        recs["automation"].append(f"{len(failed_tasks)} failed automation tasks. Attach logs and auto-open incidents for failed runs.")
    else:
        recs["automation"].append("All recent automation tasks succeeded.")

    return recs

def evaluate_simple_compliance_summary(devices: List[Dict], compliance_data: Dict) -> Dict:
    results = compliance_data.get("results", [])
    non_compliant = []
    for r in results:
        if r.get("failedRules"):
            non_compliant.append(r["deviceId"])
    return {"nonCompliant": len(non_compliant), "nonCompliantList": non_compliant}
