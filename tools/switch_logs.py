"""Pull the run logs off the console, newest first, and clear them there.

Pulls the run log off the card and summarises it.

The port keeps one log, halo.log, which it opens afresh on every run, so what
comes back is the last run and not an accumulation. Earlier it kept twenty
runs per card because the failures could not be reproduced on demand and
comparing them was the only way to characterise one; that is a development
aid and it does not belong on a player's card.

    python3 tools/switch_logs.py            # fetch, summarise, clear the card
    python3 tools/switch_logs.py 5          # ...and show the run in full
    python3 tools/switch_logs.py --keep     # fetch but leave the card alone
    python3 tools/switch_logs.py --no-fetch # just summarise what is already here
    python3 tools/switch_logs.py --atmosphere  # also fetch the port's crash reports

--atmosphere copies Atmosphere's crash reports for this program (and only
this program: the directory also holds other titles') into
/tmp/chupathingyce-logs/crash_reports/, and leaves them on the card. A run whose
report is there is summarised as the crash it was, with the faulting PC,
instead of by whatever its log last said.

Logs are removed from the card once they are safely copied, so a long
debugging session does not quietly fill it - and so that what is on the card
is always the set of runs not yet looked at.

One caveat: halo.log belongs to the run in progress. Pulling it while the
game is still going deletes the file the port has open, and the rest of that
run's output goes with it. Pull between runs, not during one.

Each log is written to /tmp/chupathingyce-logs/ and the summary is one line per run:
how far it got, where the window landed, and how it ended. heartbeat.log is
copied there too, and stays on the card (the port rewrites it every run).
"""

import ftplib
import argparse
import os
import io
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

CONSOLE = "192.168.2.173"
PORT = 5000
DIRECTORY = "/switch/ChupaThingyCE"
LOCAL = Path("/tmp/chupathingyce-logs")
RUNS_KEPT = 20
# a run lasts seconds; a report later than this after a run's start is from
# a run whose log is not here
CRASH_WITHIN = 300
PROGRAM_ID = "05446530aca7e000"
CRASH_DIRECTORY = "/atmosphere/crash_reports"
CRASHES = LOCAL / "crash_reports"
USAGE = "usage: switch_logs.py [N] [--keep] [--no-fetch] [--atmosphere]"
ROOT = Path(__file__).resolve().parent.parent
SWITCH2_LOCAL = Path("/tmp/warthog-switch2-logs")
SWITCH2_REMOTE = "/switch/warthog/logs"


def elf_symbols(path):
    """Read ELF64 function symbols without a toolchain."""
    data = path.read_bytes()
    if data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("expected a little-endian ELF64 file")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    entry_size, count = struct.unpack_from("<HH", data, 58)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, section_offset + i * entry_size)
                for i in range(count)]
    symbols = []
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name, info, _, index, value, size = struct.unpack_from("<IBBHQQ", data, offset)
            if info & 15 == 2 and index and name < len(names):
                end = names.find(b"\0", name)
                symbols.append((value, size, names[name:end].decode("utf-8", "replace")))
    return symbols


def symbolize(elf, offsets):
    if not offsets or not elf.is_file():
        return {}
    executable = shutil.which("aarch64-none-elf-addr2line")
    if executable:
        command = [executable, "-a", "-f", "-p", "-i", "-e", str(elf)]
    elif shutil.which("docker") and elf.resolve().is_relative_to(ROOT):
        command = [str(ROOT / "scripts/switch2/build.sh"), "aarch64-none-elf-addr2line",
                   "-a", "-f", "-p", "-i", "-e", str(elf.resolve().relative_to(ROOT))]
    else:
        command = None
    if command:
        result = subprocess.run(command + [hex(value) for value in offsets], capture_output=True, text=True)
        if result.returncode == 0:
            entries = re.split(r"(?m)^0x[0-9a-fA-F]+:\s*", result.stdout)[1:]
            if len(entries) == len(offsets):
                return {value: entry.strip().replace("\n", " | ")
                        for value, entry in zip(offsets, entries)}
    symbols = elf_symbols(elf)
    resolved = {}
    for address in offsets:
        matches = [(value, name) for value, size, name in symbols
                   if value <= address and (address < value + size if size else address == value)]
        if matches:
            value, name = max(matches)
            resolved[address] = "%s+0x%x" % (name, address - value)
    return resolved


def switch2_main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("WARTHOG_SWITCH2_HOST"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WARTHOG_SWITCH2_PORT", "5000")))
    parser.add_argument("--elf", type=Path, default=ROOT / "build/switch2/warthog.elf")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args(argv)
    if not args.no_fetch:
        if not args.host:
            parser.error("pass --host or set WARTHOG_SWITCH2_HOST")
        SWITCH2_LOCAL.mkdir(parents=True, exist_ok=True)
        with ftplib.FTP() as ftp:
            ftp.connect(args.host, args.port, timeout=20)
            ftp.login()
            names = ftp.nlst(SWITCH2_REMOTE)
            if "warthog.log" not in (os.path.basename(name) for name in names):
                raise FileNotFoundError("no warthog.log on the console")
            for name in names:
                name = os.path.basename(name)
                if name == "warthog.log" or name.endswith("_probe.log"):
                    data = io.BytesIO()
                    ftp.retrbinary("RETR " + SWITCH2_REMOTE + "/" + name, data.write)
                    (SWITCH2_LOCAL / name).write_bytes(data.getvalue())
    text = (SWITCH2_LOCAL / "warthog.log").read_text(encoding="utf-8", errors="replace")
    text = text.rsplit("--- launch ---", 1)[-1]
    for line in text.splitlines():
        if any(key in line.lower() for key in ("firmware:", "applet", "renderer:", "uam2", "build)", "module_base:")):
            print(line)
    faults = re.findall(r"FAULT_KIND:\s*(CPU_EXCEPTION|GPU_FAULT)", text)
    print("outcome:", faults[-1] if faults else
          ("clean exit" if "startup complete; returning" in text else "incomplete"))
    offsets = list(dict.fromkeys(int(value, 16) for value in re.findall(r"warthog\.elf\+0x([0-9a-fA-F]+)", text)))
    resolved = symbolize(args.elf, offsets)
    for value in offsets:
        print("warthog.elf+0x%x: %s" % (value, resolved.get(value, "unresolved")))


def run_number(name):
    """Sort key, for any halo.N.log left over from an older build."""
    if name == "halo.log":
        return 0
    match = re.match(r"halo\.(\d+)\.log$", name)
    return int(match.group(1)) if match else 999


def connect():
    ftp = ftplib.FTP()
    ftp.connect(CONSOLE, PORT, timeout=20)
    ftp.login()
    return ftp


def fetch(ftp, clear=True):
    """Copy the logs off the card, and remove them once they are copied.

    A file is only deleted after its bytes are here and the file is not
    empty, so a failed or truncated transfer leaves the run on the card to be
    fetched again rather than losing it."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    names = [n for n in ftp.nlst(DIRECTORY)
             if re.match(r"halo(\.\d+)?\.log$", os.path.basename(n))]
    fetched = []
    for path in names:
        data = io.BytesIO()
        try:
            ftp.retrbinary("RETR %s" % path, data.write)
        except Exception as error:
            print("could not fetch %s: %s" % (path, error))
            continue
        if not data.getvalue():
            print("%s is empty; left on the card" % path)
            continue
        name = os.path.basename(path)
        (LOCAL / name).write_bytes(data.getvalue())
        fetched.append(name)
        if clear:
            try:
                ftp.delete(path)
            except Exception as error:
                print("fetched %s but could not delete it: %s" % (path, error))
    heartbeat = io.BytesIO()
    try:
        ftp.retrbinary("RETR %s/heartbeat.log" % DIRECTORY, heartbeat.write)
        (LOCAL / "heartbeat.log").write_bytes(heartbeat.getvalue())
    except Exception as error:
        print("could not fetch heartbeat.log: %s" % error)
    return sorted(fetched, key=run_number)


def fetch_crash_reports(ftp):
    """Copy this program's crash reports that are not here yet."""
    CRASHES.mkdir(parents=True, exist_ok=True)
    try:
        names = ftp.nlst(CRASH_DIRECTORY)
    except Exception as error:
        print("could not list %s: %s" % (CRASH_DIRECTORY, error))
        return
    for path in names:
        name = os.path.basename(path)
        if not name.endswith("_%s.log" % PROGRAM_ID) or (CRASHES / name).exists():
            continue
        data = io.BytesIO()
        try:
            ftp.retrbinary("RETR %s/%s" % (CRASH_DIRECTORY, name), data.write)
        except Exception as error:
            print("could not fetch %s: %s" % (name, error))
            continue
        (CRASHES / name).write_bytes(data.getvalue())
        print("crash report %s" % name)


def crash_reports():
    """(time, path) for each local crash report, oldest first. The name
    starts with the console's clock in seconds, the clock the first line of
    a run's log is stamped with."""
    reports = []
    for path in CRASHES.glob("*_%s.log" % PROGRAM_ID):
        match = re.match(r"(\d+)_", path.name)
        if match:
            reports.append((int(match.group(1)), path))
    return sorted(reports)


def describe_crash(path):
    """'Data Abort at halo + 0x445ae8' from a crash report."""
    text = path.read_text(encoding="utf-8", errors="replace")
    kind = re.search(r"Exception Info:\s*\n\s*Type:\s*(.+)", text)
    pc = re.search(r"^\s*PC:\s*([0-9a-f]+)(?: \((.+)\))?", text, re.M)
    result = "crashed: %s" % (kind.group(1).strip() if kind else "unknown exception")
    if pc:
        result += " at %s" % (pc.group(2) or "0x" + pc.group(1))
    return result + " (%s)" % path.name


def run_start(text):
    """The console clock at the run's first line, or None."""
    match = re.match(r"\s*(\d{6,})\.\d+ ", text)
    return int(match.group(1)) if match else None


def summarise(name, crash=None):
    """One line: how long, how far, how it ended."""
    path = LOCAL / name
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    def last(pattern):
        found = [line for line in lines if re.search(pattern, line)]
        return found[-1].strip() if found else None

    window = None
    for line in lines:
        match = re.search(r"window is pinned to ([0-9a-f]+)", line)
        if match:
            window = match.group(1)
        else:
            # "Xbox memory window of 128 MB at 10000000-18000000", or the
            # older "Xbox memory window at ...": where it landed, pinned or not
            match = re.search(r"Xbox memory window (?:of \d+ MB )?at ([0-9a-f]+)-", line)
            if match:
                window = match.group(1)

    ended = "still running"
    if crash and "the game exited" in text:
        # the teardown crash: after exit(), so the exit is the news
        ended = "%s, then %s" % (last("the game exited").split(": ", 1)[-1], describe_crash(crash))
    elif crash:
        ended = describe_crash(crash)
    elif "the game exited" in text:
        ended = last("the game exited").split(": ", 1)[-1]
    elif "F halo" in text:
        ended = last("F halo").split(": ", 1)[-1]
    elif "no system call for" in text:
        ended = "guest stalled"

    calls = [int(m) for m in re.findall(r"guest heartbeat: (\d+) system calls", text)]
    return {
        "name": name,
        "lines": len(lines),
        "seconds": calls[-1] if calls else None,
        "window": window,
        "ended": ended,
        "drew": "screen:" in text,
        "start": run_start(text),
        "text": text,
    }


def main(argv):
    if "--target" in argv:
        index = argv.index("--target")
        if index + 1 >= len(argv) or argv[index + 1] not in ("switch", "switch2"):
            sys.exit("--target requires switch or switch2")
        target = argv[index + 1]
        argv = argv[:index] + argv[index + 2:]
        if target == "switch2":
            return switch2_main(argv)
    show = 0
    do_fetch = True
    clear = True
    atmosphere = False
    for argument in argv:
        if argument == "--no-fetch":
            do_fetch = False
        elif argument == "--keep":
            clear = False
        elif argument == "--atmosphere":
            atmosphere = True
        elif argument.isdigit():
            show = int(argument)
        else:
            sys.exit("unknown argument %r\n%s" % (argument, USAGE))

    if do_fetch:
        ftp = connect()
        names = fetch(ftp, clear)
        if atmosphere:
            fetch_crash_reports(ftp)
        ftp.quit()
    else:
        names = sorted((p.name for p in LOCAL.glob("halo*.log")), key=run_number)

    # each crash report belongs to the latest run that started before it
    starts = {}
    for name in names:
        text = (LOCAL / name).read_text(encoding="utf-8", errors="replace") if (LOCAL / name).exists() else ""
        starts[name] = run_start(text)
    crash_of = {}
    for time, path in crash_reports():
        owner = max((n for n in names if starts[n] is not None and starts[n] <= time <= starts[n] + CRASH_WITHIN),
                    key=lambda n: starts[n], default=None)
        if owner:
            crash_of[owner] = path

    print("%-14s %7s %9s %-10s %-5s %s" % ("run", "lines", "syscalls", "window", "drew", "ended"))
    for name in names:
        info = summarise(name, crash_of.get(name))
        if not info:
            continue
        print("%-14s %7d %9s %-10s %-5s %s" % (
            name, info["lines"],
            info["seconds"] if info["seconds"] is not None else "-",
            info["window"] or "-",
            "yes" if info["drew"] else "no",
            info["ended"]))
        if show and name == names[0]:
            print("\n--- %s ---\n" % name)
            print(info["text"])


if __name__ == "__main__":
    main(sys.argv[1:])