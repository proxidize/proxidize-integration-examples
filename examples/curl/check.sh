#!/usr/bin/env bash
set -euo pipefail

profile="${PROXY_PROFILE:-mobile}"
case "$profile" in
  mobile) prefix="MOBILE_HTTPS_PROXY" ;;
  residential) prefix="RESIDENTIAL_HTTPS_PROXY" ;;
  *)
    printf 'PROXY_PROFILE must be mobile or residential\n' >&2
    exit 2
    ;;
esac

server_name="${prefix}_SERVER"
username_name="${prefix}_USERNAME"
password_name="${prefix}_PASSWORD"
server="${!server_name:-}"
username="${!username_name:-}"
password="${!password_name:-}"

for name in "$server_name" "$username_name" "$password_name"; do
  if [[ -z "${!name:-}" ]]; then
    printf '%s is required\n' "$name" >&2
    exit 2
  fi
done

ip_check_url="${IP_CHECK_URL:-https://api.ipify.org?format=json}"
timeout="${REQUEST_TIMEOUT_SECONDS:-30}"

printf 'Client: curl\nProfile: %s\nProxy: %s\n' "$profile" "$server"
curl \
  --silent \
  --show-error \
  --fail-with-body \
  --max-time "$timeout" \
  --proxy "$server" \
  --proxy-user "$username:$password" \
  "$ip_check_url"
printf '\n'
