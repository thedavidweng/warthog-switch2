import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def available():
    return shutil.which("docker") is not None and subprocess.run(
        ["docker", "image", "inspect", "warthog-switch2-toolchain:local"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
