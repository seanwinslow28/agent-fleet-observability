#!/usr/bin/env bash
# install.sh — run the private dashboard on the Mac Mini, reachable only over Tailscale.
#
#   ./install.sh                 load com.swcb.dashboard and forward tailnet port 8780 to it
#   ./install.sh --uninstall     unload it and remove the forward
#
# The server listens on 127.0.0.1 only, so nothing on the home network reaches it.
# Tailscale's own `serve` forwards http://<mini>:8780 on the tailnet to it, which also
# keeps the macOS firewall out of the way. Idempotent: re-running replaces the job.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN="${SWCB_BRAIN:-${HOME}/Code-Brain/SWCB}"
PORT="${DASHBOARD_PORT:-8780}"
LABEL="com.swcb.dashboard"
DOMAIN="gui/$(id -u)"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UV="$(command -v uv || echo "${HOME}/.local/bin/uv")"
TAILSCALE="$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)"
LOG="${BRAIN}/.runtime/logs/dashboard.launchd.log"

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
  rm -f "${PLIST}"
  "${TAILSCALE}" serve --http="${PORT}" off 2>/dev/null || true
  echo "[dashboard install] Unloaded ${LABEL} and removed the tailnet forward on port ${PORT}."
  exit 0
fi

[[ -d "${BRAIN}/queue" ]] || { echo "No brain at ${BRAIN} (set SWCB_BRAIN)." >&2; exit 1; }
[[ -x "${UV}" ]] || { echo "uv isn't installed." >&2; exit 1; }
[[ -x "${TAILSCALE}" ]] || { echo "The Tailscale CLI isn't at ${TAILSCALE}." >&2; exit 1; }

(cd "${REPO_DIR}" && "${UV}" sync --frozen --no-dev --quiet)

# The page answers only to the Mini's own tailnet names, and only for Sean's tailnet login,
# which Tailscale serve vouches for on every request.
read -r SHORT FQDN LOGIN < <("${TAILSCALE}" status --self --json | /usr/bin/python3 -c '
import json, sys
d = json.load(sys.stdin)
fqdn = d["Self"]["DNSName"].rstrip(".")
print(fqdn.split(".")[0], fqdn, d["User"][str(d["Self"]["UserID"])]["LoginName"])')
[[ -n "${LOGIN:-}" ]] || { echo "Couldn't read this machine's tailnet name and login; is Tailscale up?" >&2; exit 1; }
mkdir -p "$(dirname "${LOG}")"

cat > "${PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key><array>
    <string>${UV}</string>
    <string>run</string>
    <string>--frozen</string>
    <string>--no-dev</string>
    <string>--quiet</string>
    <string>python</string>
    <string>-m</string>
    <string>dashboard.server</string>
    <string>--brain</string>
    <string>${BRAIN}</string>
    <string>--bind</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>${PORT}</string>
    <string>--allow-host</string>
    <string>${SHORT}:${PORT}</string>
    <string>--allow-host</string>
    <string>${FQDN}:${PORT}</string>
    <string>--require-user</string>
    <string>${LOGIN}</string>
  </array>
  <key>WorkingDirectory</key><string>${REPO_DIR}</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:${HOME}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>LANG</key><string>en_US.UTF-8</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>${LOG}</string>
  <key>StandardErrorPath</key><string>${LOG}</string>
</dict></plist>
PLIST
plutil -lint "${PLIST}" >/dev/null

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
for _ in 1 2 3 4 5 6 7 8 9 10; do  # bootstrap right after bootout can fail with "5: Input/output error"
  launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || break
  sleep 1
done
launchctl bootstrap "${DOMAIN}" "${PLIST}"
"${TAILSCALE}" serve --bg --http="${PORT}" "http://127.0.0.1:${PORT}"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -H "Tailscale-User-Login: ${LOGIN}" "http://127.0.0.1:${PORT}/api/review" >/dev/null 2>&1; then
    echo "[dashboard install] ${LABEL} is up: http://${SHORT}:${PORT} on the tailnet."
    exit 0
  fi
  sleep 1
done
echo "[dashboard install] ${LABEL} didn't answer within 10 seconds; see ${LOG}." >&2
exit 1
