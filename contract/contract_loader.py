import os
import yaml
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import ValidationError

from contract.contract_entry import ContractEntry

logger = logging.getLogger(__name__)


class ContractLoadError(Exception):
    """Raised when contract loading fails."""

    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Any] = None):
        self.message = message
        self.file_path = file_path
        self.details = details
        full_message = f"{message}"
        if file_path:
            full_message += f" [File: {file_path}]"
        if details:
            full_message += f"\nDetails:\n{details}"
        super().__init__(full_message)


class ContractConflictError(Exception):
    """Raised when duplicate route definitions are found."""
    def __init__(self, message: str):
        super().__init__(message)


class ContractLoader:
    """Loads and validates contract entries from YAML files or dictionaries."""

    @staticmethod
    def load_from_file(file_path: Union[str, Path]) -> List[ContractEntry]:
        file_path = Path(file_path)
        if not file_path.exists():
            raise ContractLoadError("Contract file not found", str(file_path))

        try:
            with file_path.open("r", encoding="utf-8") as f:
                yaml_content = yaml.safe_load(f)
            return ContractLoader.load_from_dict(yaml_content, file_path)
        except yaml.YAMLError as e:
            raise ContractLoadError("Failed to parse YAML", str(file_path), e)
        except Exception as e:
            if isinstance(e, ContractLoadError):
                raise
            raise ContractLoadError("Unexpected error during file load", str(file_path), e)

    @staticmethod
    def load_from_dict(data: Dict[str, Any], source: Optional[Union[str, Path]] = None) -> List[ContractEntry]:
        source_str = str(source) if source else "dictionary"

        if not isinstance(data, dict):
            raise ContractLoadError("Contract data must be a dictionary", source_str)

        routes_data = data.get("routes") or data.get("entries")
        if not isinstance(routes_data, list):
            raise ContractLoadError("Routes must be provided as a list", source_str)

        validated_entries = []
        validation_errors = []

        for i, entry_data in enumerate(routes_data):
            try:
                if "id" not in entry_data and "method" in entry_data and "path" in entry_data:
                    entry_data["id"] = f"{entry_data['method']}_{entry_data['path'].replace('/', '_').replace('{', '').replace('}', '')}"
                entry = ContractEntry.parse_obj(entry_data)
                validated_entries.append(entry)
            except ValidationError as e:
                validation_errors.append(f"Entry #{i + 1}:\n{str(e)}")

        if validation_errors:
            raise ContractLoadError(
                f"Contract validation failed with {len(validation_errors)} error(s)",
                source_str,
                "\n\n".join(validation_errors)
            )

        return validated_entries

    @staticmethod
    def load_from_directory(directory_path: Union[str, Path]) -> List[ContractEntry]:
        directory_path = Path(directory_path)
        if not directory_path.exists() or not directory_path.is_dir():
            raise ContractLoadError("Directory not found or not a directory", str(directory_path))

        all_entries = []
        errors = []

        for file_path in directory_path.glob("**/*.yaml"):
            try:
                entries = ContractLoader.load_from_file(file_path)
                all_entries.extend(entries)
                logger.info(f"✅ Loaded {len(entries)} contract entries from {file_path}")
            except ContractLoadError as e:
                logger.warning(f"⚠️ Failed to load {file_path}: {e.message}")
                errors.append(f"{file_path}: {e.message}")

        if not all_entries and errors:
            raise ContractLoadError(
                f"Failed to load any valid contracts from directory. Encountered {len(errors)} error(s).",
                str(directory_path),
                "\n".join(errors)
            )

        return all_entries
