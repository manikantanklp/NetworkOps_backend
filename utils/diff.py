# real-appli-back/utils/diff.py
from typing import List, Dict

def get_before_after_for_device(device_id: str, backups: List[Dict]):
    """
    Return (before, after) last two backup entries for device_id.
    """
    filtered = [b for b in backups if b["deviceId"] == device_id]
    if not filtered or len(filtered) < 2:
        return None
    sorted_b = sorted(filtered, key=lambda x: x["timestamp"])
    return sorted_b[-2], sorted_b[-1]

def compute_diff_summary(before: Dict, after: Dict):
    """
    Very simple "semantic" diff summary: show added/removed/modified strings
    (We treat 'changes' arrays as bullet list.)
    """
    before_set = set(before.get("changes", []))
    after_set = set(after.get("changes", []))
    added = list(after_set - before_set)
    removed = list(before_set - after_set)
    common = list(before_set & after_set)
    return {"added": added, "removed": removed, "common": common}
