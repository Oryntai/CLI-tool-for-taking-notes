from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from notes_cli.cli import app

runner = CliRunner()


@pytest.fixture(params=["sqlite", "json"])
def backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def init_env(home_dir: Path, backend: str) -> dict[str, str]:
    env = {"NOTES_CLI_HOME": str(home_dir)}
    result = runner.invoke(app, ["init", "--backend", backend], env=env)
    assert result.exit_code == 0, result.output
    return env


def run_cli(env: dict[str, str], args: list[str], input_data: str | None = None):
    return runner.invoke(app, args, env=env, input=input_data)


def test_add_list_view(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    add_result = run_cli(
        env,
        ["add", "Buy milk and bread", "--title", "Groceries", "--tags", "home,shop"],
    )
    assert add_result.exit_code == 0
    assert "Created note 1" in add_result.output

    list_result = run_cli(env, ["list", "--format", "json"])
    assert list_result.exit_code == 0
    notes = json.loads(list_result.stdout)
    assert len(notes) == 1
    assert notes[0]["title"] == "Groceries"
    assert notes[0]["tags"] == ["home", "shop"]

    view_result = run_cli(env, ["view", "1", "--format", "json"])
    assert view_result.exit_code == 0
    note = json.loads(view_result.stdout)
    assert note["body"] == "Buy milk and bread"


def test_add_from_stdin(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    add_result = run_cli(
        env,
        ["add", "--stdin", "--title", "stdin note"],
        input_data="hello from pipe",
    )
    assert add_result.exit_code == 0

    view_result = run_cli(env, ["view", "1", "--format", "json"])
    note = json.loads(view_result.stdout)
    assert note["title"] == "stdin note"
    assert note["body"] == "hello from pipe"


def test_search_with_tag_filter(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "Milk for coffee", "--tags", "food"])
    run_cli(env, ["add", "Draft status report", "--tags", "work"])

    search_result = run_cli(env, ["search", "milk", "--format", "json"])
    assert search_result.exit_code == 0
    notes = json.loads(search_result.stdout)
    assert len(notes) == 1
    assert "Milk" in notes[0]["body"]

    tagged_result = run_cli(env, ["search", "milk", "--tag", "food", "--format", "json"])
    assert tagged_result.exit_code == 0
    tagged = json.loads(tagged_result.stdout)
    assert len(tagged) == 1


def test_archive_and_unarchive(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "Archive me"])

    archive_result = run_cli(env, ["archive", "1"])
    assert archive_result.exit_code == 0

    active_list = run_cli(env, ["list", "--format", "json"])
    assert active_list.exit_code == 0
    assert json.loads(active_list.stdout) == []

    archived_list = run_cli(env, ["list", "--archived", "--format", "json"])
    assert archived_list.exit_code == 0
    archived_notes = json.loads(archived_list.stdout)
    assert len(archived_notes) == 1

    all_list = run_cli(env, ["list", "--all", "--format", "json"])
    assert all_list.exit_code == 0
    assert len(json.loads(all_list.stdout)) == 1

    unarchive_result = run_cli(env, ["unarchive", "1"])
    assert unarchive_result.exit_code == 0

    active_again = run_cli(env, ["list", "--format", "json"])
    assert active_again.exit_code == 0
    notes = json.loads(active_again.stdout)
    assert len(notes) == 1


def test_pin_unpin_and_filter(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "one"])
    run_cli(env, ["add", "two"])

    pin_result = run_cli(env, ["pin", "2"])
    assert pin_result.exit_code == 0

    pinned_list = run_cli(env, ["list", "--pinned", "--format", "json"])
    notes = json.loads(pinned_list.stdout)
    assert len(notes) == 1
    assert notes[0]["id"] == 2

    unpin_result = run_cli(env, ["unpin", "2"])
    assert unpin_result.exit_code == 0

    pinned_empty = run_cli(env, ["list", "--pinned", "--format", "json"])
    assert json.loads(pinned_empty.stdout) == []


def test_edit_with_flags(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "old body", "--title", "old title", "--tags", "x"])

    edit_result = run_cli(
        env,
        ["edit", "1", "--title", "new title", "--body", "new body", "--tags", "a,b,b"],
    )
    assert edit_result.exit_code == 0

    view_result = run_cli(env, ["view", "1", "--format", "json"])
    note = json.loads(view_result.stdout)
    assert note["title"] == "new title"
    assert note["body"] == "new body"
    assert note["tags"] == ["a", "b"]


def test_delete_with_yes(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "delete me"])
    delete_result = run_cli(env, ["delete", "1", "--yes"])
    assert delete_result.exit_code == 0

    view_result = run_cli(env, ["view", "1"])
    assert view_result.exit_code == 1
    assert "not found" in view_result.output.lower()


def test_export_import_skip_and_overwrite(tmp_path: Path, backend: str) -> None:
    source_env = init_env(tmp_path / "source-home", backend)
    target_env = init_env(tmp_path / "target-home", backend)

    run_cli(source_env, ["add", "body one", "--title", "one"])
    run_cli(source_env, ["add", "body two", "--title", "two", "--pin"])
    run_cli(source_env, ["archive", "2"])

    export_path = tmp_path / "backup" / "notes-export.json"
    export_result = run_cli(source_env, ["export", "--out", str(export_path)])
    assert export_result.exit_code == 0
    assert export_path.exists()

    first_import = run_cli(target_env, ["import", "--in", str(export_path), "--mode", "skip"])
    assert first_import.exit_code == 0
    assert "inserted=2" in first_import.output

    second_import = run_cli(target_env, ["import", "--in", str(export_path), "--mode", "skip"])
    assert second_import.exit_code == 0
    assert "skipped=2" in second_import.output

    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload[0]["body"] = "updated from import"
    export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    overwrite_import = run_cli(
        target_env,
        ["import", "--in", str(export_path), "--mode", "overwrite"],
    )
    assert overwrite_import.exit_code == 0
    assert "updated=2" in overwrite_import.output

    view_result = run_cli(target_env, ["view", "1", "--format", "json"])
    note = json.loads(view_result.stdout)
    assert note["body"] == "updated from import"


def test_import_invalid_payload_fails_cleanly(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    bad_path = tmp_path / "bad.json"
    bad_path.write_text(
        json.dumps([
            {
                "id": 1,
                "title": "broken",
                "body": "",
                "tags": ["x"],
            }
        ]),
        encoding="utf-8",
    )

    result = run_cli(env, ["import", "--in", str(bad_path)])
    assert result.exit_code == 1
    assert "Import item #1" in result.output


def test_info_reports_stats(tmp_path: Path, backend: str) -> None:
    env = init_env(tmp_path / "home", backend)

    run_cli(env, ["add", "first", "--pin"])
    run_cli(env, ["add", "second"])
    run_cli(env, ["archive", "2"])

    result = run_cli(env, ["info", "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["backend"] == backend
    assert data["initialized"] is True
    assert data["total_notes"] == 2
    assert data["active_notes"] == 1
    assert data["archived_notes"] == 1
    assert data["pinned_notes"] == 1


def test_commands_fail_before_init(tmp_path: Path) -> None:
    env = {"NOTES_CLI_HOME": str(tmp_path / "home")}
    result = runner.invoke(app, ["list"], env=env)
    assert result.exit_code == 1
    assert "Run `notes init` first" in result.output
