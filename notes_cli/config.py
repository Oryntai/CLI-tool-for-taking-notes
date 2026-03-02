from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BackendType = Literal["sqlite", "json"]


@dataclass(slots=True)
class RuntimeConfig:
    backend: BackendType
    data_dir: Path
    home_dir: Path

    @property
    def config_file(self) -> Path:
        return self.home_dir / "config.json"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "notes.db"

    @property
    def json_path(self) -> Path:
        return self.data_dir / "notes.json"

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "data_dir": str(self.data_dir),
            "home_dir": str(self.home_dir),
            "config_file": str(self.config_file),
        }


def get_home_dir() -> Path:
    env_home = os.getenv("NOTES_CLI_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    if sys.platform.startswith("win"):
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata).resolve() / "notes-cli"

    return Path.home() / ".local" / "share" / "notes-cli"


def _default_config() -> RuntimeConfig:
    home_dir = get_home_dir()
    return RuntimeConfig(backend="sqlite", data_dir=home_dir, home_dir=home_dir)


def _payload_to_runtime(payload: dict[str, str], *, fallback: RuntimeConfig) -> RuntimeConfig:
    backend_raw = payload.get("backend", fallback.backend)
    backend: BackendType = "json" if backend_raw == "json" else "sqlite"
    data_dir_raw = payload.get("data_dir")
    data_dir = Path(data_dir_raw).expanduser().resolve() if data_dir_raw else fallback.data_dir
    return RuntimeConfig(backend=backend, data_dir=data_dir, home_dir=fallback.home_dir)


def _runtime_to_payload(cfg: RuntimeConfig) -> dict[str, str]:
    return {"backend": cfg.backend, "data_dir": str(cfg.data_dir)}


def load_config() -> RuntimeConfig:
    default = _default_config()
    config_file = default.config_file
    if not config_file.exists():
        return default

    payload = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return default

    safe_payload = {
        "backend": str(payload.get("backend", default.backend)),
        "data_dir": str(payload.get("data_dir", default.data_dir)),
    }
    return _payload_to_runtime(safe_payload, fallback=default)


def save_config(backend: BackendType, data_dir: Path) -> RuntimeConfig:
    base = _default_config()
    cfg = RuntimeConfig(backend=backend, data_dir=data_dir.resolve(), home_dir=base.home_dir)
    cfg.home_dir.mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    payload = _runtime_to_payload(cfg)
    cfg.config_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cfg


def config_exists() -> bool:
    return _default_config().config_file.exists()


def reset_config() -> RuntimeConfig:
    default = _default_config()
    if default.config_file.exists():
        default.config_file.unlink()
    return default


def read_raw_config() -> dict[str, str | bool]:
    cfg = load_config()
    payload: dict[str, str | bool] = dict(cfg.as_dict())
    payload["config_exists"] = config_exists()
    return payload


def parse_backend(raw: str) -> BackendType:
    normalized = raw.strip().lower()
    if normalized not in {"sqlite", "json"}:
        raise ValueError("Backend must be 'sqlite' or 'json'.")
    return normalized  # type: ignore[return-value]
