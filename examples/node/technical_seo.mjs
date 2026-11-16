// Audit a URL with the 27 checks of the Semust Technical SEO API (Node.js 18+, no dependencies).
//
//   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//   node technical_seo.mjs https://www.wikipedia.org/

const API = "https://data.semust.com";
const HEADERS = {
  "Content-Type": "application/json",
  "SEMUST-API-USER": process.env.SEMUST_API_USER,
  "SEMUST-API-PASSWORD": process.env.SEMUST_API_PASSWORD,
};
const WAIT = 60; // seconds the API holds the request open before answering 202

const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));

// POST a request and return the final response, polling if the API answers 202.
async function call(path, payload) {
  let resp = await fetch(`${API}${path}?wait=${WAIT}`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout((WAIT + 30) * 1000),
  });
  while (resp.status === 202) {
    const task = await resp.json();
    await sleep(Number(resp.headers.get("Retry-After") ?? 5));
    resp = await fetch(task.poll_url, { headers: HEADERS });
  }
  return resp;
}

const url = process.argv[2] ?? "https://www.wikipedia.org/";
const resp = await call("/v1/technical-seo", {
  url, // full URL, including https://
  // proxy_country: "US", // optional: fetch the page from this country
});

if (resp.status !== 200) {
  console.error(`Error ${resp.status}: ${await resp.text()}`);
  process.exit(1);
}

const report = await resp.json();
const s = report.summary;
console.log(`${url}\nScore ${s.score}/100 · ${s.passed_checks}/${s.total_checks} checks passed`);
for (const [category, checks] of Object.entries(report.audit_results)) {
  for (const [name, check] of Object.entries(checks)) {
    if (check.status !== "pass") {
      console.log(`  [${check.severity.padEnd(8)}] ${category}.${name}: ${check.issue ?? ""}`);
    }
  }
}
