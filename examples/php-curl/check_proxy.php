<?php

declare(strict_types=1);

function required(string $name): string
{
    $value = trim((string) getenv($name));
    if ($value === '') {
        throw new RuntimeException("{$name} is required");
    }
    return $value;
}

$profile = strtolower(trim((string) (getenv('PROXY_PROFILE') ?: 'mobile')));
$prefix = match ($profile) {
    'mobile' => 'MOBILE_HTTPS_PROXY',
    'residential' => 'RESIDENTIAL_HTTPS_PROXY',
    default => throw new RuntimeException('PROXY_PROFILE must be mobile or residential'),
};

$server = required("{$prefix}_SERVER");
$parts = parse_url($server);
if ($parts === false || !in_array($parts['scheme'] ?? '', ['http', 'https'], true)) {
    throw new RuntimeException("{$prefix}_SERVER must use http:// or https://");
}
if (isset($parts['user']) || isset($parts['pass'])) {
    throw new RuntimeException("{$prefix}_SERVER must not contain credentials");
}

$checkUrl = trim((string) (getenv('IP_CHECK_URL') ?: 'https://api.ipify.org?format=json'));
$client = curl_init($checkUrl);
curl_setopt_array($client, [
    CURLOPT_PROXY => $server,
    CURLOPT_PROXYUSERNAME => required("{$prefix}_USERNAME"),
    CURLOPT_PROXYPASSWORD => required("{$prefix}_PASSWORD"),
    CURLOPT_CONNECTTIMEOUT => (int) (getenv('REQUEST_TIMEOUT_SECONDS') ?: 30),
    CURLOPT_TIMEOUT => (int) (getenv('REQUEST_TIMEOUT_SECONDS') ?: 30),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FAILONERROR => true,
]);

$payload = curl_exec($client);
if ($payload === false) {
    throw new RuntimeException(curl_error($client), curl_errno($client));
}
curl_close($client);

$decoded = json_decode($payload, true);
$ip = is_array($decoded) ? ($decoded['ip'] ?? '') : trim($payload);
if (filter_var($ip, FILTER_VALIDATE_IP) === false) {
    throw new RuntimeException('Unexpected IP-check response');
}

printf("Profile: %s\nProxy: %s\nExit IP: %s\n", $profile, $server, $ip);
