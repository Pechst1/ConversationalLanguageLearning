#!/usr/bin/env bash
# Install Playwright's Chromium and its system packages (run from web-frontend/).
#
# The normal path is unchanged: `npx playwright install --with-deps chromium`. On 11 Nov
# 2026 every walk job failed for hours at that step with «Temporary failure resolving
# 'azure.archive.ubuntu.com'» (apt exit 100) while GitHub reported no incident: the
# runner's apt goes through `mirror+file:/etc/apt/apt-mirrors.txt`, whose first mirror
# is Azure's. Only when the normal install fails, apt is pointed at Ubuntu's own
# archive (and security.ubuntu.com for the security pocket), refreshed, and the install
# runs once more. A second failure fails the step.
set -uo pipefail

if npx playwright install --with-deps chromium; then
  exit 0
fi

echo "::warning::Playwright's install failed (apt mirror?); retrying with archive.ubuntu.com and security.ubuntu.com"
codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg
sources=/etc/apt/sources.list.d/ubuntu.sources
if [ -f "$sources" ]; then
  sudo cp "$sources" "$sources.walk-backup"
  sudo tee "$sources" > /dev/null <<SOURCES
Types: deb
URIs: http://archive.ubuntu.com/ubuntu/
Suites: ${codename} ${codename}-updates ${codename}-backports
Components: main restricted universe multiverse
Signed-By: ${keyring}

Types: deb
URIs: http://security.ubuntu.com/ubuntu/
Suites: ${codename}-security
Components: main restricted universe multiverse
Signed-By: ${keyring}
SOURCES
else
  # An older image with a classic sources.list.
  sudo sed -i -E \
    -e 's#mirror\+file:[^ ]+#http://archive.ubuntu.com/ubuntu/#' \
    -e 's#https?://[a-z.]*azure\.archive\.ubuntu\.com/ubuntu/?#http://archive.ubuntu.com/ubuntu/#' \
    /etc/apt/sources.list
fi
echo 'Acquire::Retries "5";' | sudo tee /etc/apt/apt.conf.d/80-walk-retries > /dev/null
sudo apt-get update -o Acquire::Retries=5 || true
npx playwright install --with-deps chromium
