from __future__ import annotations

def first_difference(a, b, path="$"):
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            child=f"{path}.{key}"
            if key not in a: return child, "<missing>", b[key]
            if key not in b: return child, a[key], "<missing>"
            diff=first_difference(a[key], b[key], child)
            if diff is not None: return diff
        return None
    if isinstance(a, list):
        if len(a)!=len(b): return f"{path}.length", len(a), len(b)
        for i,(left,right) in enumerate(zip(a,b)):
            diff=first_difference(left,right,f"{path}[{i}]")
            if diff is not None: return diff
        return None
    if a!=b: return path,a,b
    return None
