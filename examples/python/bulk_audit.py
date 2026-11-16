"""Audit a list of URLs with the Semust Technical SEO API and write one CSV row per URL.

    pip install requests
    export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
    python bulk_audit.py urls.txt                  # one URL per line
    python bulk_audit.py https://www.wikipedia.org/ https://en.wikipedia.org/wiki/Search_engine_optimization --workers 4

Each URL is one request (from $0.0012). Errors are written to the CSV and are not charged.
"""
import argparse
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://data.semust.com"
HEADERS = {
    "SEMUST-API-USER": os.environ["SEMUST_API_USER"],
    "SEMUST-API-PASSWORD": os.environ["SEMUST_API_PASSWORD"],
}
WAIT = 60
COLUMNS = ["url", "score", "passed_checks", "critical_issues", "warning_issues", "notice_issues",
           "critical", "warning", "notice", "error"]


def call(path, payload):
    resp = requests.post(f"{API}{path}", params={"wait": WAIT}, json=payload,
                         headers=HEADERS, timeout=WAIT + 30)
    while resp.status_code == 202:
        task = resp.json()
        time.sleep(int(resp.headers.get("Retry-After", 5)))
        resp = requests.get(task["poll_url"], headers=HEADERS, timeout=30)
    return resp


def audit(url):
    """Audit one URL and flatten the report into a CSV row."""
    row = {"url": url}
    try:
        resp = call("/v1/technical-seo", {"url": url})
    except requests.RequestException as e:
        return {**row, "error": str(e)}
    if resp.status_code != 200:
        return {**row, "error": f"{resp.status_code} {resp.text[:200].strip()}"}

    report = resp.json()
    row.update({k: report["summary"][k] for k in COLUMNS[1:6]})
    failed = {"critical": [], "warning": [], "notice": []}
    for category, checks in report["audit_results"].items():
        for name, check in checks.items():
            if check["status"] == "fail":
                failed.setdefault(check["severity"], []).append(f"{name}:{check.get('issue', '')}")
    for severity in ("critical", "warning", "notice"):
        row[severity] = "; ".join(failed[severity])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+", help="URLs, or a text file with one URL per line")
    ap.add_argument("--out", default="technical_seo_audit.csv")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests")
    args = ap.parse_args()

    urls = []
    for item in args.urls:
        path = Path(item)
        if path.is_file():
            urls += [line.strip() for line in path.read_text().splitlines()
                     if line.strip() and not line.startswith("#")]
        else:
            urls.append(item)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(audit, urls))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        status = row.get("error") or f"score {row['score']:>3}  critical: {row['critical'] or '-'}"
        print(f"{row['url']}\n    {status}")
    print(f"\n{len(rows)} URLs written to {args.out}")


if __name__ == "__main__":
    main()
