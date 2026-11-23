using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text.Json;

static string Required(string name)
{
    var value = Environment.GetEnvironmentVariable(name)?.Trim();
    return string.IsNullOrEmpty(value) ? throw new ArgumentException($"{name} is required") : value;
}

var profile = (Environment.GetEnvironmentVariable("PROXY_PROFILE") ?? "mobile").Trim().ToLowerInvariant();
var prefix = profile switch
{
    "mobile" => "MOBILE_HTTPS_PROXY",
    "residential" => "RESIDENTIAL_HTTPS_PROXY",
    _ => throw new ArgumentException("PROXY_PROFILE must be mobile or residential"),
};

var proxyUri = new Uri(Required($"{prefix}_SERVER"));
if (proxyUri.Scheme != Uri.UriSchemeHttp || !string.IsNullOrEmpty(proxyUri.UserInfo))
    throw new ArgumentException($"{prefix}_SERVER must be a credential-free http:// endpoint");

var proxy = new WebProxy(proxyUri)
{
    Credentials = new NetworkCredential(Required($"{prefix}_USERNAME"), Required($"{prefix}_PASSWORD")),
};
using var handler = new HttpClientHandler { Proxy = proxy, UseProxy = true };
using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(30) };

var checkUrl = Environment.GetEnvironmentVariable("IP_CHECK_URL") ?? "https://api.ipify.org?format=json";
using var response = await client.GetAsync(checkUrl);
response.EnsureSuccessStatusCode();
var payload = await response.Content.ReadAsStringAsync();
var ip = payload.Trim();
try
{
    ip = JsonDocument.Parse(payload).RootElement.GetProperty("ip").GetString() ?? "";
}
catch (JsonException) { }
if (!IPAddress.TryParse(ip, out _)) throw new InvalidDataException("Unexpected IP-check response");

Console.WriteLine($"Profile: {profile}");
Console.WriteLine($"Proxy: {proxyUri}");
Console.WriteLine($"Exit IP: {ip}");
