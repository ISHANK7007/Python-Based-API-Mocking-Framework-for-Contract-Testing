# contract/contract_version.py

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class ContractVersion:
    name: str
    version: str
    file_path: str
    release_date: datetime = None

    VERSION_PATTERN = re.compile(r"(.+)-v(\d+)\.(\d+)\.(\d+)\.yaml")

    @classmethod
    def from_file_path(cls, path: str):
        match = cls.VERSION_PATTERN.search(path)
        if not match:
            raise ValueError(f"Invalid versioned file name: {path}")
        name, major, minor, patch = match.groups()
        version = f"v{int(major)}.{int(minor)}.{int(patch)}"
        return cls(
            name=name,
            version=version,
            file_path=path,
            release_date=datetime.now()
        )

    def __lt__(self, other):
        return list(map(int, self.version[1:].split('.'))) < list(map(int, other.version[1:].split('.')))

    def __str__(self):
        return f"{self.name} {self.version}"
