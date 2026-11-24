"""Write personal data atomically with private permissions on POSIX."""

from pathlib import Path
from tempfile import NamedTemporaryFile


def write_private(path, contents):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp_path = Path(stream.name)
        try:
            stream.write(contents)
            stream.close()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
