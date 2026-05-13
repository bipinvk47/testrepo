Optional large codebase for perf / static-analysis runs (not tracked in git).

1) Clone a shallow copy of Django (Python, tens of MB, thousands of modules):

   Windows (PowerShell, from repo root):
     powershell -ExecutionPolicy Bypass -File scripts/clone_performance_fixture.ps1

   macOS/Linux:
     bash scripts/clone_performance_fixture.sh

2) Include cloned sources in snapshot (slow — may take minutes):
     python scripts/whitebox_metrics.py --root . --with-benchmark-fixture -o metrics/whitebox_report.json

Leave this directory empty until you clone; your tool output should jump in LOC/function counts once the fixture is present.
