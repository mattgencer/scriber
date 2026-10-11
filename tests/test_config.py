from __future__ import annotations

from pathlib import Path

import pytest

from scriber.config import ConfigError, Layout, OutputFormat, load_defaults_dict, load_settings


def test_packaged_defaults_load_without_any_other_source() -> None:
    settings = load_settings()
    assert settings.model.name == "large-v3"
    assert settings.paths.input_dir == Path("input")
    assert settings.output.layout is Layout.PER_FILE_FOLDER
    assert settings.output.formats == [OutputFormat.TXT, OutputFormat.SRT, OutputFormat.JSON]
    assert ".mp4" in settings.media.extensions
    assert ".m4a" in settings.media.extensions
    assert settings.hf_token is None


def test_local_toml_overrides_defaults_and_merges_deeply(isolated_env: Path) -> None:
    (isolated_env / "scriber.toml").write_text('[model]\nlanguage = "hi"\n', encoding="utf-8")
    settings = load_settings()
    assert settings.model.language == "hi"
    assert settings.model.name == "large-v3"  # untouched sibling key survives the merge


def test_explicit_config_beats_local_and_must_exist(isolated_env: Path, tmp_path: Path) -> None:
    (isolated_env / "scriber.toml").write_text('[model]\nlanguage = "hi"\n', encoding="utf-8")
    explicit = tmp_path / "other.toml"
    explicit.write_text('[model]\nlanguage = "de"\n', encoding="utf-8")
    assert load_settings(explicit).model.language == "de"
    with pytest.raises(ConfigError):
        load_settings(tmp_path / "missing.toml")


def test_config_env_var_selects_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chosen = tmp_path / "env.toml"
    chosen.write_text('[model]\nlanguage = "fr"\n', encoding="utf-8")
    monkeypatch.setenv("SCRIBER_CONFIG", str(chosen))
    assert load_settings().model.language == "fr"


def test_env_beats_toml_and_nested_delimiter_works(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (isolated_env / "scriber.toml").write_text('[model]\nlanguage = "hi"\n', encoding="utf-8")
    monkeypatch.setenv("SCRIBER_MODEL__LANGUAGE", "es")
    monkeypatch.setenv("SCRIBER_MODEL__BATCH_SIZE", "4")
    settings = load_settings()
    assert settings.model.language == "es"
    assert settings.model.batch_size == 4


def test_cli_overrides_beat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRIBER_MODEL__LANGUAGE", "es")
    settings = load_settings(overrides={"model": {"language": "it"}})
    assert settings.model.language == "it"


def test_hf_token_from_standard_and_prefixed_env_stays_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_standard")
    settings = load_settings()
    assert settings.hf_token is not None
    assert settings.hf_token.get_secret_value() == "hf_standard"
    assert "hf_standard" not in repr(settings)
    monkeypatch.setenv("SCRIBER_HF_TOKEN", "hf_prefixed")
    assert load_settings().hf_token.get_secret_value() == "hf_prefixed"  # type: ignore[union-attr]


def test_hf_token_read_from_dotenv(isolated_env: Path) -> None:
    (isolated_env / ".env").write_text("HF_TOKEN=hf_from_dotenv\n", encoding="utf-8")
    token = load_settings().hf_token
    assert token is not None
    assert token.get_secret_value() == "hf_from_dotenv"


def test_invalid_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        load_settings(overrides={"model": {"batch_size": 0}})


def test_defaults_dict_matches_loaded_defaults() -> None:
    assert load_defaults_dict()["model"]["name"] == load_settings().model.name


def test_user_config_file_is_read_from_the_os_config_dir(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    user_file = tmp_path / "user-dir" / "config.toml"
    user_file.parent.mkdir()
    user_file.write_text('[model]\nlanguage = "pt"\n', encoding="utf-8")
    monkeypatch.setattr("scriber.config.user_config_path", lambda: user_file)
    assert load_settings().model.language == "pt"
    (isolated_env / "scriber.toml").write_text('[model]\nlanguage = "nl"\n', encoding="utf-8")
    assert load_settings().model.language == "nl"  # project file beats the per-user file


def test_tilde_in_configured_paths_is_expanded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings = load_settings(overrides={"paths": {"input_dir": "~/media", "output_dir": "~/out"}})
    assert settings.paths.input_dir == tmp_path / "media"
    assert settings.paths.output_dir == tmp_path / "out"
