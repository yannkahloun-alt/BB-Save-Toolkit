"""Static release-archive contract checks. Usage: python tools/verify_release_zip.py path.zip"""
from __future__ import annotations
import sys, zipfile
from pathlib import PurePosixPath

FORBIDDEN_PARTS={'__pycache__','.pytest_cache'}

def audit_members(names):
    issues=[]
    for name in names:
        p=PurePosixPath(name)
        if any(part in FORBIDDEN_PARTS for part in p.parts) or p.suffix=='.pyc':
            issues.append(f'cache artifact: {name}')
    archetypes=[n for n in names if PurePosixPath(n).name.startswith('archetypes') and PurePosixPath(n).suffix=='.json']
    if len(archetypes)!=1 or PurePosixPath(archetypes[0]).name!='archetypes.json':
        issues.append(f'archetype configs: {archetypes}')
    return issues

def audit_zip(path):
    with zipfile.ZipFile(path) as zf: return audit_members(zf.namelist())

def main(argv=None):
    argv=argv or sys.argv[1:]
    if len(argv)!=1:
        print('Usage: python tools/verify_release_zip.py <release.zip>'); return 2
    issues=audit_zip(argv[0])
    if issues:
        print('\n'.join(issues)); return 1
    print('release archive OK'); return 0
if __name__=='__main__': raise SystemExit(main())
