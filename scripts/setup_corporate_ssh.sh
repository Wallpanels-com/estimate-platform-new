#!/bin/bash
# Run interactively on the Mac. This never changes the personal SSH config.
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
corporate_key="$HOME/.ssh/id_ed25519_wallpanels_estimate_new"
corporate_config="$HOME/.ssh/config_wallpanels_estimate_new"

if [ -e "$corporate_key" ] || [ -e "$corporate_key.pub" ] || [ -e "$corporate_config" ]; then
  echo "Corporate SSH files already exist. Preserved them; review docs/corporate-release.md."
  exit 1
fi
mkdir -p "$HOME/.ssh"
ssh-keygen -t ed25519 -a 100 -C 'WallPanels Estimate Platform corporate access' -f "$corporate_key"
# Noclobber prevents races from overwriting an existing configuration file.
(set -o noclobber
  printf '%s\n' \
    'Host github-wallpanels-estimate-new' \
    '  HostName github.com' \
    '  User git' \
    "  IdentityFile $corporate_key" \
    '  IdentitiesOnly yes' \
    '  IdentityAgent none' \
    "  UserKnownHostsFile $HOME/.ssh/known_hosts_wallpanels_estimate_new" \
    '  StrictHostKeyChecking ask' > "$corporate_config"
)
chmod 600 "$corporate_config"
git -C "$project_root" config --local core.sshCommand "ssh -F '$corporate_config'"
git -C "$project_root" remote set-url origin git@github-wallpanels-estimate-new:Wallpanels-com/estimate-platform-new.git
echo 'Corporate key created. Only copy the .pub file into the CORPORATE GitHub account.'
echo 'No push was performed. See docs/corporate-release.md for verification.'
