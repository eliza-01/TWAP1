from __future__ import annotations

import subprocess
import sys

from env_profile import generate_env_files, project_root

DEFAULT_ARGS = ["--profile", "server", "up", "-d", "--build"]


def main() -> int:
    root = project_root()
    runtime = generate_env_files(root)
    args = sys.argv[1:] or DEFAULT_ARGS
    cmd = ["docker", "compose", "--env-file", str(root / ".env.compose.generated"), *args]

    print(
        "Docker Compose profile:",
        f"{runtime['APP_ENV']} / {runtime['PUBLIC_DOMAIN']} / "
        f"Site:{runtime['SIGNAL_SERVER_PORT']} Signal:{runtime['SIGNAL_SERVER_PORT']}",
    )
    try:
        return subprocess.run(cmd, cwd=root).returncode
    except FileNotFoundError:
        print("Docker не найден. Установите Docker Desktop или запустите команду на машине с docker compose.", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())