"""Verify source archives and the installed CLI outside the checkout."""

import subprocess
import sys
import tarfile
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="romwiki-package-") as directory:
        temporary = Path(directory)
        distribution = temporary / "dist"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(distribution),
                str(ROOT),
            ],
            check=True,
        )
        with tarfile.open(next(distribution.glob("*.tar.gz"))) as archive:
            names = archive.getnames()
            for document in ("docs/development.md", "docs/operations.md"):
                if not any(name.endswith(f"/{document}") for name in names):
                    raise RuntimeError(f"Source archive is missing {document}")
        environment = temporary / "venv"
        venv.EnvBuilder(with_pip=False).create(environment)
        binaries = environment / ("Scripts" if sys.platform == "win32" else "bin")
        python = binaries / ("python.exe" if sys.platform == "win32" else "python")
        wheel = next(distribution.glob("*.whl"))
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--python",
                str(python),
                "install",
                "--no-deps",
                str(wheel),
            ],
            check=True,
        )
        subprocess.run(
            [str(python), "-m", "romwiki", "--help"], cwd=temporary, check=True
        )
        command = binaries / ("romwiki.exe" if sys.platform == "win32" else "romwiki")
        subprocess.run([str(command), "--help"], cwd=temporary, check=True)
        subprocess.run(
            [
                str(python),
                "-c",
                "from pathlib import Path; import romwiki; "
                "assert Path(romwiki.__file__).is_relative_to(Path('venv').resolve()); "
                "assert romwiki.__version__",
            ],
            cwd=temporary,
            check=True,
        )


if __name__ == "__main__":
    main()
