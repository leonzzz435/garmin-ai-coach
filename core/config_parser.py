import json
import getpass
from pathlib import Path
from typing import Any

import yaml


class ConfigParser:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        content = self.config_path.read_text(encoding="utf-8")

        if self.config_path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(content)
        if self.config_path.suffix == ".json":
            return json.loads(content)
        raise ValueError(f"Unsupported config format: {self.config_path.suffix}")

    def get_athlete_info(self) -> tuple[str, str]:
        if not (email := self.config.get("athlete", {}).get("email")):
            raise ValueError("Athlete email is required in config file")

        return self.config.get("athlete", {}).get("name", "Athlete"), email

    def get_contexts(self) -> tuple[str, str]:
        return (
            self.config.get("context", {}).get("analysis", "").strip(),
            self.config.get("context", {}).get("planning", "").strip(),
        )

    def get_extraction_config(self) -> dict[str, Any]:
        return {
            "activities_days": self.config.get("extraction", {}).get("activities_days", 7),
            "metrics_days": self.config.get("extraction", {}).get("metrics_days", 14),
            "ai_mode": self.config.get("extraction", {}).get("ai_mode", "development"),
            "enable_plotting": self.config.get("extraction", {}).get("enable_plotting", False),
            "hitl_enabled": self.config.get("extraction", {}).get("hitl_enabled", True),
            "skip_synthesis": self.config.get("extraction", {}).get("skip_synthesis", False),
        }

    def get_competitions(self) -> list[dict[str, Any]]:
        competitions = self.config.get("competitions", [])
        return [
            {
                "name": comp.get("name", ""),
                "date": comp.get("date", ""),
                "race_type": comp.get("race_type", ""),
                "priority": comp.get("priority", "B"),
                "target_time": comp.get("target_time", ""),
            }
            for comp in competitions
        ]

    def get_output_directory(self) -> Path:
        return Path(self.config.get("output", {}).get("directory", "./data"))

    def get_password(self) -> str:
        return (
            self.config.get("credentials", {}).get("password", "")
            or getpass.getpass("Enter Garmin Connect password: ")
        )
