#!/usr/bin/env python3
"""Copy the Switch build to the console over FTP.

The console runs an FTP server from its Homebrew Menu, so a build can be put
on the card and run without taking it out. That makes the edit-build-run
loop a matter of one command and a wait, rather than a card reader.

Usage: python3 tools/switch_deploy.py [--host 192.168.2.173] [--port 5000]
                                     [--destination /switch/ChupaThingyCE]
                                     [--user anonymous] [--password ...]
                                     [build/switch/halo.nro ...]

With no files, it uploads what the port needs: the program, the guest
image (halo_guest.elf, with the deko3d renderer), internet play's
brokers.txt, and the Switch's own menu files (build/switch/menus,
tools/switch_menus.py) into menus/, as a release carries them.
The game's own data (maps/) is not touched - it is large, it does not change
between builds, and it belongs to the player rather than to the build.

    python3 tools/switch_deploy.py --target switch2 --build

is the Switch 2 loop in one command: scripts/switch2/build.sh configure and
build, then tools/switch_package.py lays the card out, then the result is
uploaded to /switch/warthog/. Without --build it uploads the build that is
already there (build/switch2/warthog.nro, the broker list, and the menu files
when the build writes them).

The console's address comes from --host and --port, or from
WARTHOG_SWITCH2_HOST and WARTHOG_SWITCH2_PORT, so no command line and no
committed file has to carry it.
"""

import argparse
import ftplib
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_HOST = "192.168.2.173"
DEFAULT_PORT = 5000
DEFAULT_DESTINATION = "/switch/ChupaThingyCE"

# the Switch 2 card folder (CARD_DIR in port/switch2/build.py)
SWITCH2_DESTINATION = "/switch/warthog"
SWITCH2_HOST_VARIABLE = "WARTHOG_SWITCH2_HOST"
SWITCH2_PORT_VARIABLE = "WARTHOG_SWITCH2_PORT"
SWITCH2_PORT = 5000
SWITCH2_BUILD = Path("scripts") / "switch2" / "build.sh"
SWITCH2_BUILD_OUTPUT = Path("build") / "switch2"
# what tools/switch_package.py lays out, and the program's folder inside it
SWITCH2_PACKAGE = SWITCH2_BUILD_OUTPUT / "package"
SWITCH2_PACKAGED_APP = SWITCH2_PACKAGE / "switch" / "warthog"
BROKERS = Path("chupathingyce") / "port" / "assets" / "network" / "brokers.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path,
                        help="files to upload; the default is the program and the guest images")
    parser.add_argument("--target", choices=("switch", "switch2"), default="switch",
                        help="which console to deploy to (default: switch)")
    parser.add_argument("--build", action="store_true",
                        help="switch2 only: build and package first, so one command is the whole loop")
    parser.add_argument("--host", default=None,
                        help="the console's address (switch2: default %s)" % SWITCH2_HOST_VARIABLE)
    parser.add_argument("--port", type=int, default=None,
                        help="its FTP port (switch2: default %s, else %d)"
                        % (SWITCH2_PORT_VARIABLE, SWITCH2_PORT))
    parser.add_argument("--destination", default=None,
                        help="the card folder to upload into (default: the target's)")
    parser.add_argument("--user", default="anonymous")
    parser.add_argument("--password", default=None,
                        help="anonymous by default, which is what the console's server uses")
    args = parser.parse_args()

    if args.target == "switch2":
        return deploy_switch2(args)
    return deploy_switch(args)


def deploy_switch(args: argparse.Namespace) -> int:
    """the original Switch's card folder: the program, the guest, the menus"""
    args.host = args.host or DEFAULT_HOST
    args.port = args.port or DEFAULT_PORT
    args.destination = args.destination or DEFAULT_DESTINATION

    # (and internet play's brokers, which a release carries beside the
    # game: without them the server browser lists nothing)
    files = args.files or [Path("build/switch/halo.nro"), Path("build/switch/halo_guest.elf"),
                          Path("chupathingyce/port/assets/network/brokers.txt")]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print("not built: " + ", ".join(missing), file=sys.stderr)
        return 1

    ftp = connect(args.host, args.port, args.user, args.password)
    if ftp is None:
        return 1

    try:
        ftp.cwd(args.destination)
    except ftplib.error_perm as error:
        print("no %s on the card: %s" % (args.destination, error), file=sys.stderr)
        ftp.quit()
        return 1

    upload(ftp, args.destination, files)
    if not args.files:
        menus_upload(ftp, args.destination, Path("build/switch/menus"))
    ftp.quit()
    print("done")
    return 0


def connect(host: str, port: int, user: str, password) -> ftplib.FTP:
    """a logged-in session with the console's server, or None with the
    reason on stderr"""
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password or "anonymous@")
        return ftp
    except (OSError, ftplib.Error) as error:
        print("cannot reach the console's FTP server at %s:%d: %s" % (host, port, error),
              file=sys.stderr)
        return None


def upload(ftp: ftplib.FTP, destination: str, files) -> None:
    """each file straight over the old one, with the size checked after

    The first version uploaded to name.new and renamed over the top, on the
    reasoning that a failure part way through would leave the old program
    runnable. That reasoning was wrong in the case that mattered: this
    server refuses to rename onto an existing file, so the fallback deleted
    the target first - which opens a window in which neither the old name
    nor the new one exists, and loses the program if anything goes wrong in
    it. A direct STOR replaces the file in one step, which is checked to
    work here and has no such window. The cost is that a transfer cut short
    leaves a truncated file rather than an old one, which is why the size is
    compared afterwards.
    """
    for path in files:
        print("%s -> %s/%s (%.1f MB)" % (path, destination, path.name, path.stat().st_size / 1048576.0))
        with path.open("rb") as handle:
            ftp.storbinary("STOR " + path.name, handle)
        expected = path.stat().st_size
        actual = ftp.size(path.name)
        if actual != expected:
            print("warning: %s is %d bytes on the card, %d expected; the transfer was cut short"
                  % (path.name, actual, expected), file=sys.stderr)


def deploy_switch2(args: argparse.Namespace) -> int:
    """the Switch 2 loop: build and package if asked, then upload the program

    One command (`--build`) is build, package and deploy, so a console test
    is a single line rather than three that can be run out of order.
    """
    args.destination = args.destination or SWITCH2_DESTINATION
    args.host = args.host or os.environ.get(SWITCH2_HOST_VARIABLE)
    if not args.host:
        print("no console address: pass --host <switch2-ip> or set %s" % SWITCH2_HOST_VARIABLE,
              file=sys.stderr)
        return 1
    args.port = args.port or int(os.environ.get(SWITCH2_PORT_VARIABLE) or SWITCH2_PORT)

    if args.build:
        result = subprocess.run([str(SWITCH2_BUILD), "configure"], check=False)
        result = result if result.returncode else subprocess.run([str(SWITCH2_BUILD), "build"], check=False)
        result = result if result.returncode else subprocess.run(
            [sys.executable, str(Path(__file__).parent / "switch_package.py"),
             "--target", "switch2", "--out", str(SWITCH2_PACKAGE)], check=False)
        if result.returncode:
            print("the build or the package failed; nothing was uploaded", file=sys.stderr)
            return result.returncode

    app = SWITCH2_PACKAGED_APP if args.build else SWITCH2_BUILD_OUTPUT
    nro = app / "warthog.nro"
    if not nro.is_file():
        print("no %s: run `scripts/switch2/build.sh build` and `tools/switch_package.py "
              "--target switch2 --out %s`, or pass --build" % (nro, SWITCH2_PACKAGE), file=sys.stderr)
        return 1

    # the package is the card folder, so what it holds is what goes over:
    # the program, the broker list, and the menu files when there are any
    files = [nro]
    for extra in ((app / "brokers.txt") if args.build else BROKERS,):
        if extra.is_file():
            files.append(extra)
    menus = sorted((app / "menus").rglob("*.xml")) \
        if (app / "menus").is_dir() else []

    ftp = connect(args.host, args.port, args.user, args.password)
    if ftp is None:
        return 1
    if not make_destination(ftp, args.destination):
        ftp.quit()
        return 1
    upload(ftp, args.destination, files)
    for path in menus:
        relative = path.relative_to(app).as_posix()
        folder = args.destination + "/" + relative.rsplit("/", 1)[0]
        if not make_destination(ftp, folder):
            ftp.quit()
            return 1
        upload(ftp, folder, [path])
    ftp.quit()
    print("done")
    return 0


def make_destination(ftp: ftplib.FTP, destination: str) -> bool:
    """change into a card folder, making each missing part of it

    The console's server refuses MKD for a folder that is already there, so
    that answer is the ordinary one and not an error.
    """
    parts = [part for part in destination.split("/") if part]
    for depth in range(1, len(parts) + 1):
        folder = "/" + "/".join(parts[:depth])
        try:
            ftp.cwd(folder)
        except ftplib.error_perm:
            try:
                ftp.mkd(folder)
                ftp.cwd(folder)
            except ftplib.Error as error:
                print("cannot make %s on the card: %s" % (folder, error), file=sys.stderr)
                return False
    return True


def menus_upload(ftp: ftplib.FTP, destination: str, menus: Path) -> None:
    """the Switch's menu files into menus/ below the destination, their
    folders made as needed (the server's MKD fails for one that is there)"""
    files = sorted(menus.rglob("*.xml")) if menus.is_dir() else []
    if not files:
        print("no menu files in %s (ninja switch writes them); the card's are left as they are" % menus)
        return
    # (a menu file of an earlier build that this one does not write would
    # go on replacing the game's: taken off the card)
    wanted = set(path.relative_to(menus).as_posix() for path in files)
    for folder, name in card_menu_files(ftp, destination + "/menus"):
        if folder[len(destination) + len("/menus"):].lstrip("/") + ("/" if folder != destination + "/menus" else "") + name not in wanted:
            print("%s/%s: not in this build; removed from the card" % (folder, name))
            ftp.delete(folder + "/" + name)
    made = set()
    for path in files:
        relative = path.relative_to(menus)
        folder = destination + "/menus" + "".join("/" + part for part in relative.parent.parts if part != ".")
        if folder not in made:
            parts = folder.split("/")
            for depth in range(len(destination.split("/")) + 1, len(parts) + 1):
                try:
                    ftp.mkd("/".join(parts[:depth]))
                except ftplib.error_perm:
                    pass
            made.add(folder)
        ftp.cwd(folder)
        print("%s -> %s/%s" % (path, folder, path.name))
        with path.open("rb") as handle:
            ftp.storbinary("STOR " + path.name, handle)
    ftp.cwd(destination)


def card_menu_files(ftp: ftplib.FTP, folder: str) -> list:
    """the .xml files below the card's menus folder, as (folder, name), two
    levels deep (the game's own layout); none when the folder is not there"""
    found = []
    try:
        ftp.cwd(folder)
    except ftplib.error_perm:
        return found
    entries = []
    ftp.retrlines("LIST", entries.append)
    for entry in entries:
        parts = entry.split(None, 8)
        if len(parts) < 9:
            continue
        name = parts[8]
        if entry.startswith("d"):
            inner = []
            ftp.cwd(folder + "/" + name)
            ftp.retrlines("LIST", inner.append)
            for line in inner:
                words = line.split(None, 8)
                if len(words) == 9 and not line.startswith("d") and words[8].endswith(".xml"):
                    found.append((folder + "/" + name, words[8]))
            ftp.cwd(folder)
        elif name.endswith(".xml"):
            found.append((folder, name))
    return found


if __name__ == "__main__":
    raise SystemExit(main())