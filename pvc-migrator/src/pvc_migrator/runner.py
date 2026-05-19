from __future__ import annotations

import subprocess


class CommandRunner:
    def run(self, command: str) -> None:
        subprocess.run(command, shell=True, check=True)
