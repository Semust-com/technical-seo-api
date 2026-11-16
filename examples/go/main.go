// Audit a URL with the 27 checks of the Semust Technical SEO API (Go 1.21+, standard library only).
//
//	export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//	go run . https://www.wikipedia.org/
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strconv"
	"time"
)

const (
	api  = "https://data.semust.com"
	wait = 60 // seconds the API holds the request open before answering 202
)

type check struct {
	Status   string `json:"status"`
	Severity string `json:"severity"`
	Issue    string `json:"issue"`
}

type report struct {
	URL          string                      `json:"url"`
	AuditResults map[string]map[string]check `json:"audit_results"`
	Summary      struct {
		TotalChecks    int `json:"total_checks"`
		PassedChecks   int `json:"passed_checks"`
		CriticalIssues int `json:"critical_issues"`
		Score          int `json:"score"`
	} `json:"summary"`
	Cost float64 `json:"cost"`
}

var client = &http.Client{Timeout: (wait + 30) * time.Second}

func send(method, url string, body []byte) (*http.Response, []byte, error) {
	req, err := http.NewRequest(method, url, bytes.NewReader(body))
	if err != nil {
		return nil, nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("SEMUST-API-USER", os.Getenv("SEMUST_API_USER"))
	req.Header.Set("SEMUST-API-PASSWORD", os.Getenv("SEMUST_API_PASSWORD"))
	resp, err := client.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	return resp, data, err
}

// call POSTs a request and returns the final response, polling if the API answers 202.
func call(path string, payload any) (int, []byte, error) {
	body, _ := json.Marshal(payload)
	resp, data, err := send(http.MethodPost, fmt.Sprintf("%s%s?wait=%d", api, path, wait), body)
	for err == nil && resp.StatusCode == http.StatusAccepted {
		var task struct {
			PollURL string `json:"poll_url"`
		}
		if err = json.Unmarshal(data, &task); err != nil {
			break
		}
		retry, convErr := strconv.Atoi(resp.Header.Get("Retry-After"))
		if convErr != nil {
			retry = 5
		}
		time.Sleep(time.Duration(retry) * time.Second)
		resp, data, err = send(http.MethodGet, task.PollURL, nil)
	}
	if err != nil {
		return 0, nil, err
	}
	return resp.StatusCode, data, nil
}

func main() {
	url := "https://www.wikipedia.org/"
	if len(os.Args) > 1 {
		url = os.Args[1]
	}
	status, data, err := call("/v1/technical-seo", map[string]any{
		"url": url, // full URL, including https://
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "request failed:", err)
		os.Exit(1)
	}
	if status != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Error %d: %s\n", status, data)
		os.Exit(1)
	}

	var r report
	if err := json.Unmarshal(data, &r); err != nil {
		fmt.Fprintln(os.Stderr, "decode:", err)
		os.Exit(1)
	}
	fmt.Printf("%s\nScore %d/100 · %d/%d checks passed · %d critical\n",
		url, r.Summary.Score, r.Summary.PassedChecks, r.Summary.TotalChecks, r.Summary.CriticalIssues)

	categories := make([]string, 0, len(r.AuditResults))
	for c := range r.AuditResults {
		categories = append(categories, c)
	}
	sort.Strings(categories)
	for _, c := range categories {
		for name, ch := range r.AuditResults[c] {
			if ch.Status != "pass" {
				fmt.Printf("  [%-8s] %s.%s: %s\n", ch.Severity, c, name, ch.Issue)
			}
		}
	}
}
