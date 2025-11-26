# real-appli-back/utils/compliance.py
from typing import List, Dict

def evaluate_compliance_overview(devices: List[Dict], compliance_data: Dict) -> Dict:
    """
    Evaluate and summarize compliance, using provided compliance.json (rules + results)
    """
    rules = {r["id"]: r for r in compliance_data.get("rules", [])}
    results = compliance_data.get("results", [])
    device_map = {d["id"]: d for d in devices}
    summary = {"totalDevices": len(devices), "compliant":0, "warning":0, "nonCompliant":0, "devices": []}
    for res in results:
        did = res["deviceId"]
        device = device_map.get(did, {"id":did,"name":did,"complianceStatus":"unknown"})
        failed = res.get("failed", res.get("failedRules", []))
        status = "compliant" if len(failed)==0 else "non-compliant"
        # some heuristics: if few failed and low severity then 'warning'
        sev = 0
        for f in failed:
            r = rules.get(f)
            if r:
                if r["severity"]=="high": sev += 3
                elif r["severity"]=="medium": sev += 2
                else: sev += 1
        if len(failed)>0 and sev<=2:
            status = "warning"
        summary_key = "compliant" if status=="compliant" else ("warning" if status=="warning" else "nonCompliant")
        if status=="compliant":
            summary["compliant"] += 1
        elif status=="warning":
            summary["warning"] += 1
        else:
            summary["nonCompliant"] += 1
        summary["devices"].append({
            "deviceId": did,
            "deviceName": device.get("name"),
            "status": status,
            "failedRules": [rules.get(f, {}).get("name", f) for f in failed]
        })
    # overall compliance percent
    overall_percent = int(round((summary["compliant"]/summary["totalDevices"])*100))
    summary["overallCompliancePercent"] = overall_percent
    return summary
