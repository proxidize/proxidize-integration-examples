package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

func required(name string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		panic(name + " is required")
	}
	return value
}

func main() {
	profile := strings.ToLower(strings.TrimSpace(os.Getenv("PROXY_PROFILE")))
	if profile == "" {
		profile = "mobile"
	}
	prefixes := map[string]string{
		"mobile":      "MOBILE_HTTPS_PROXY",
		"residential": "RESIDENTIAL_HTTPS_PROXY",
	}
	prefix, ok := prefixes[profile]
	if !ok {
		panic("PROXY_PROFILE must be mobile or residential")
	}

	proxyURL, err := url.Parse(required(prefix + "_SERVER"))
	if err != nil || proxyURL.Hostname() == "" || (proxyURL.Scheme != "http" && proxyURL.Scheme != "https") {
		panic(prefix + "_SERVER must use http:// or https://")
	}
	if proxyURL.User != nil {
		panic(prefix + "_SERVER must not contain credentials")
	}
	proxyURL.User = url.UserPassword(required(prefix+"_USERNAME"), required(prefix+"_PASSWORD"))

	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = http.ProxyURL(proxyURL)
	client := &http.Client{Transport: transport, Timeout: 30 * time.Second}
	defer transport.CloseIdleConnections()

	checkURL := os.Getenv("IP_CHECK_URL")
	if checkURL == "" {
		checkURL = "https://api.ipify.org?format=json"
	}
	response, err := client.Get(checkURL)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode > 299 {
		panic(fmt.Sprintf("IP check returned %s", response.Status))
	}
	payload, err := io.ReadAll(io.LimitReader(response.Body, 64*1024))
	if err != nil {
		panic(err)
	}
	var result struct {
		IP string `json:"ip"`
	}
	if json.Unmarshal(payload, &result) != nil || net.ParseIP(strings.TrimSpace(result.IP)) == nil {
		result.IP = strings.TrimSpace(string(payload))
	}
	if net.ParseIP(result.IP) == nil {
		panic("unexpected IP-check response")
	}

	redacted := *proxyURL
	redacted.User = nil
	fmt.Printf("Profile: %s\nProxy: %s\nExit IP: %s\n", profile, redacted.String(), result.IP)
}
