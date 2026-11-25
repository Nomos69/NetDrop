#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

for command in python3 dpkg-deb dpkg-query ldd readelf; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$command" >&2
    exit 1
  fi
done

if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo 'Install python3-tk for the selected Python interpreter, then retry.' >&2
  exit 1
fi

architecture="$(dpkg --print-architecture)"
if [ "$architecture" != "amd64" ]; then
  printf 'Only Ubuntu amd64 is supported; detected %s.\n' "$architecture" >&2
  exit 1
fi

version="${NETDROP_PACKAGE_VERSION:-0.1.0}"
version="${version#v}"
if [[ ! "$version" =~ ^[0-9]+([.][0-9]+)*$ ]]; then
  printf 'Package version must be numeric, optionally with dots: %s\n' "$version" >&2
  exit 1
fi

venv="$project_root/.build-venv-linux"
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install -r requirements.txt -r requirements-packaging.txt

"$venv/bin/pyinstaller" --noconfirm --clean \
  --distpath "$project_root/dist/linux" \
  --workpath "$project_root/build/linux" \
  packaging/NetDropLocal.spec

bundle="$project_root/dist/linux/NetDropLocal"
package_root="$project_root/build/linux/deb-root"
output="$project_root/dist/installer/NetDrop-Local-Ubuntu.deb"
if [ ! -x "$bundle/NetDropLocal" ]; then
  printf 'PyInstaller output is missing: %s\n' "$bundle/NetDropLocal" >&2
  exit 1
fi
rm -rf "$package_root"
install -d "$package_root/DEBIAN" \
  "$package_root/opt/netdrop-local" \
  "$package_root/usr/bin" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/icons/hicolor/scalable/apps"
cp -a "$bundle/." "$package_root/opt/netdrop-local/"
install -m 755 packaging/netdrop-local "$package_root/usr/bin/netdrop-local"
install -m 644 packaging/netdrop-local.desktop "$package_root/usr/share/applications/netdrop-local.desktop"
install -m 644 static/logo.svg "$package_root/usr/share/icons/hicolor/scalable/apps/netdrop-local.svg"

declare -A dependencies=()
while IFS= read -r -d '' binary; do
  if ! readelf -h "$binary" >/dev/null 2>&1; then
    continue
  fi
  if ! ldd_output="$(ldd "$binary" 2>&1)"; then
    if grep -q 'not a dynamic executable' <<< "$ldd_output"; then
      continue
    fi
    printf 'Unable to inspect runtime dependencies of %s:\n%s\n' "$binary" "$ldd_output" >&2
    exit 1
  fi
  if grep -q 'not found' <<< "$ldd_output"; then
    printf 'Unresolved runtime dependency in %s:\n%s\n' "$binary" "$ldd_output" >&2
    exit 1
  fi
  while IFS= read -r library; do
    [ -n "$library" ] || continue
    case "$library" in
      "$bundle"/*) continue ;;
    esac
    resolved="$(readlink -f "$library")"
    owner="$(dpkg-query -S "$resolved" 2>/dev/null | sed -n '1{s/: .*//; s/:.*//; p;}')"
    if [ -z "$owner" ]; then
      printf 'Could not identify the Ubuntu package providing %s\n' "$resolved" >&2
      exit 1
    fi
    dependencies["$owner"]=1
  done < <(awk '/=> \// {print $3} /^[[:space:]]*\/.* \(0x/ {print $1}' <<< "$ldd_output")
done < <(find "$bundle" -type f -print0)

depends="$(printf '%s\n' "${!dependencies[@]}" | sort -u | paste -sd, -)"
if [ -z "$depends" ]; then
  echo 'Could not determine package runtime dependencies.' >&2
  exit 1
fi

installed_size="$(du -sk "$package_root" | cut -f1)"
cat > "$package_root/DEBIAN/control" <<EOF
Package: netdrop-local
Version: $version
Section: net
Priority: optional
Architecture: amd64
Installed-Size: $installed_size
Maintainer: NetDrop Project
Depends: $depends
Description: Local network file and clipboard sharing
 NetDrop Local hosts temporary sharing rooms on a private Wi-Fi or LAN.
EOF

mkdir -p "$(dirname "$output")"
rm -f "$output"
dpkg-deb --build --root-owner-group "$package_root" "$output"
printf 'Ubuntu installer created at %s\n' "$output"
