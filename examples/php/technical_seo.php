<?php
// Audit a URL with the 27 checks of the Semust Technical SEO API (PHP 7.4+ with the curl extension).
//
//   export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//   php technical_seo.php https://www.wikipedia.org/

const API = "https://data.semust.com";
const WAIT = 60; // seconds the API holds the request open before answering 202

function request(string $method, string $url, ?array $payload = null): array
{
    $ch = curl_init($url);
    $headers = [];
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => WAIT + 30,
        CURLOPT_HTTPHEADER => [
            "Content-Type: application/json",
            "SEMUST-API-USER: " . getenv("SEMUST_API_USER"),
            "SEMUST-API-PASSWORD: " . getenv("SEMUST_API_PASSWORD"),
        ],
        CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$headers) {
            $parts = explode(":", $line, 2);
            if (count($parts) === 2) {
                $headers[strtolower(trim($parts[0]))] = trim($parts[1]);
            }
            return strlen($line);
        },
    ]);
    if ($payload !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    }
    $body = curl_exec($ch);
    if ($body === false) {
        fwrite(STDERR, "Request failed: " . curl_error($ch) . "\n");
        exit(1);
    }
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$status, $headers, $body];
}

// POST a request and return the final response, polling if the API answers 202.
function call(string $path, array $payload): array
{
    [$status, $headers, $body] = request("POST", API . $path . "?wait=" . WAIT, $payload);
    while ($status === 202) {
        $task = json_decode($body, true);
        sleep((int)($headers["retry-after"] ?? 5));
        [$status, $headers, $body] = request("GET", $task["poll_url"]);
    }
    return [$status, $body];
}

$url = $argv[1] ?? "https://www.wikipedia.org/";
[$status, $body] = call("/v1/technical-seo", [
    "url" => $url, // full URL, including https://
    // "proxy_country" => "US", // optional: fetch the page from this country
]);

if ($status !== 200) {
    fwrite(STDERR, "Error {$status}: {$body}\n");
    exit(1);
}

$report = json_decode($body, true);
$s = $report["summary"];
printf("%s\nScore %d/100 · %d/%d checks passed\n", $url, $s["score"], $s["passed_checks"], $s["total_checks"]);
foreach ($report["audit_results"] as $category => $checks) {
    foreach ($checks as $name => $check) {
        if ($check["status"] !== "pass") {
            printf("  [%-8s] %s.%s: %s\n", $check["severity"], $category, $name, $check["issue"] ?? "");
        }
    }
}
