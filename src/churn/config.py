"""Config loading helpers. All thresholds/paths/seeds come from configs/config.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "config.yaml"


@lru_cache(maxsize=4)
def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else CONFIG_PATH
    cfg = yaml.safe_load(p.read_text())
    cfg["_root"] = str(ROOT)
    return cfg


def dataset_cfg(cfg: dict) -> dict:
    return cfg["datasets"][cfg["active_dataset"]]


def ensure_dirs(cfg: dict) -> None:
    for key in ("interim", "processed", "artifacts", "reports"):
        (ROOT / cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
