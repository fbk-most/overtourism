from typing import Any, Dict, List
# ================================================================
# Nested helpers (these work unchanged)
# ================================================================

def _nested_get(d: dict, keys: List[Any], final_key: str):
    cur = d
    for k in keys:
        if k not in cur:
            raise KeyError(f"[DEBUG][_nested_get] Missing key {k} while traversing keys={keys}")
        cur = cur[k]
    if final_key not in cur:
        raise KeyError(f"[DEBUG][_nested_get] Missing final key '{final_key}' in dict at path {keys}")
    return cur[final_key]


def _nested_set(d: dict, keys: List[Any], final_key: str, value: Any):
    cur = d
    for k in keys:
        cur = cur.setdefault(k, {})
    cur[final_key] = value
    return d
