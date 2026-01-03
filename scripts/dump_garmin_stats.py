#!/usr/bin/env python3
import argparse
import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

from core.config_parser import ConfigParser
from services.garmin.client import GarminConnectClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dump Garmin get_stats payload for a date to a JSON file."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML or JSON config (recommended).",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("GARMIN_EMAIL"),
        help="Garmin account email (or set GARMIN_EMAIL). Ignored when --config is provided.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("GARMIN_PASSWORD"),
        help="Garmin account password (or set GARMIN_PASSWORD). Ignored when --config is provided.",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date to fetch (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path. Defaults to ./garmin_stats_<date>.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_path: Path | None = None
    if args.config:
        config = ConfigParser(Path(args.config))
        _, email = config.get_athlete_info()
        password = config.get_password()
        output_path = config.get_output_directory() / f"garmin_stats_{args.date}.json"
    else:
        email = args.email
        password = args.password

    if not email or not password:
        raise SystemExit(
            "Missing credentials: provide --config or set --email/--password (or GARMIN_EMAIL/GARMIN_PASSWORD)."
        )

    output_path = Path(args.output) if args.output else output_path
    output_path = (output_path or Path(f"garmin_stats_{args.date}.json")).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = GarminConnectClient()
    client.connect(email, password)
    raw_stats = client.client.get_stats(args.date) or {}
    raw_profile = client.client.get_user_profile() or {}
    raw_sleep = client.client.get_sleep_data(args.date) or {}

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base = output_path.with_suffix("")
    outputs = {
        "user_profile": base.with_name(f"{base.name}_user_profile.json"),
        "stats": base.with_name(f"{base.name}_stats.json"),
        "sleep_data": base.with_name(f"{base.name}_sleep_data.json"),
    }

    payloads = {
        "user_profile": {"fetched_at": fetched_at, "data": raw_profile},
        "stats": {"date": args.date, "fetched_at": fetched_at, "data": raw_stats},
        "sleep_data": {"date": args.date, "fetched_at": fetched_at, "data": raw_sleep},
    }

    for key, path in outputs.items():
        path.write_text(json.dumps(payloads[key], indent=2), encoding="utf-8")
        logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
