#!/bin/sh
# Warthog for Switch 2: configure, build and audit, in the pinned toolchain.
#
#   scripts/switch2/build.sh [image|configure|build|audit|<command>] [args...]
#
#     image       build the toolchain image scripts/switch2/Dockerfile describes
#     configure   configure.py with --console-port port/switch2
#     build       configure, then `ninja switch2`
#     audit       tools/switch2_audit.py on build/switch2
#     <command>   any other command, run inside the toolchain
#
# The repository is mounted at /src and the commands run there, so the
# linker map carries /src/... and never the build machine's home directory
# (tools/switch2_audit.py fails the build's artifacts when it finds one).
#
# A host with the same packages installed can run it without Docker:
# WARTHOG_SWITCH2_NATIVE=1. Inside the image it is detected, so `build.sh
# build` from the image's own shell does not try to nest Docker.
#
# SPDX-License-Identifier: GPL-3.0-or-later

set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
image=${WARTHOG_SWITCH2_IMAGE:-warthog-switch2-toolchain:local}
command=${1:-build}
if [ $# -gt 0 ]; then
	shift
fi

usage() {
	cat <<'EOF'
usage: scripts/switch2/build.sh [image|configure|build|audit|<command>] [args...]

  image       build the toolchain image (scripts/switch2/Dockerfile)
  configure   run configure.py with --console-port port/switch2
  build       configure, then `ninja switch2`
  audit       check build/switch2's artifacts (tools/switch2_audit.py)
  <command>   run any other command inside the toolchain

WARTHOG_SWITCH2_IMAGE names the image (default warthog-switch2-toolchain:local);
WARTHOG_SWITCH2_NATIVE=1 runs the commands on this host instead of in Docker.
EOF
}

native() {
	[ -e /.dockerenv ] || [ "${WARTHOG_SWITCH2_NATIVE:-0}" = 1 ]
}

run() {
	if native; then
		cd "$root"
		"$@"
	else
		docker run --rm -i \
			-v "$root:/src" \
			-w /src \
			--user "$(id -u):$(id -g)" \
			-e HOME=/tmp \
			"$image" "$@"
	fi
}

case "$command" in
	-h|--help|help)
		usage
		;;
	image)
		# the Dockerfile's build context is the repository: it copies
		# port/switch2/uam2.patch into the uam2 build
		docker build -f "$root/scripts/switch2/Dockerfile" -t "$image" "$root"
		;;
	configure)
		run python3 chupathingyce/configure.py --console-port port/switch2 "$@"
		;;
	build)
		run python3 chupathingyce/configure.py --console-port port/switch2
		run ninja switch2
		;;
	audit)
		run python3 tools/switch2_audit.py build/switch2
		;;
	*)
		run "$command" "$@"
		;;
esac
