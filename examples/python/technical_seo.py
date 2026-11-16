"""Audit a URL with the 27 checks of the Semust Technical SEO API.

    pip install requests
    export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
    python technical_seo.py https://www.wikipedia.org/
"""
import json
import os
import sys
import time

import requests

API = "https://data.semust.com"
HEADERS = {
    "SEMUST-API-USER": os.environ["SEMUST_API_USER"],
    "SEMUST-API-PASSWORD": os.environ["SEMUST_API_PASSWORD"],
}
WAIT = 60  # seconds the API holds the request open before answering 202
SEVERITY_ORDER = {"critical": 0, "warning": 1, "notice": 2}


def call(path, payload):
    """POST a request and return the final response, polling if the API answers 202."""
    resp = requests.post(f"{API}{path}", params={"wait": WAIT}, json=payload,
                         headers=HEADERS, timeout=WAIT + 30)
    while resp.status_code == 202:
        task = resp.json()
        time.sleep(int(resp.headers.get("Retry-After", 5)))
        resp = requests.get(task["poll_url"], headers=HEADERS, timeout=30)
    return resp


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.wikipedia.org/"
    resp = call("/v1/technical-seo", {
        "url": url,                 # full URL, including https://
        # "proxy_country": "US",    # optional: fetch the page from this country
    })
    if resp.status_code != 200:
        sys.exit(f"Error {resp.status_code}: {resp.text}")

    report = resp.json()
    s = report["summary"]
    print(f"{url}\nScore {s['score']}/100 · {s['passed_checks']}/{s['total_checks']} checks passed · "
          f"{s['critical_issues']} critical, {s['warning_issues']} warning, {s['notice_issues']} notice")

    failed = [(check["severity"], category, name, check.get("issue", ""))
              for category, checks in report["audit_results"].items()
              for name, check in checks.items() if check["status"] != "pass"]
    for severity, category, name, issue in sorted(failed, key=lambda f: SEVERITY_ORDER.get(f[0], 9)):
        print(f"  [{severity:<8}] {category}.{name}: {issue}")

    with open("technical_seo_result.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nFull response saved to technical_seo_result.json")


if __name__ == "__main__":
    main()
