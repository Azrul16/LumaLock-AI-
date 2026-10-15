from lumalock.core.config import load_settings


def test_new_pipeline_migrates_speed_profile_and_retains_license(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "pipeline_version: 2\nedit_budget_seconds: 1800\nquality_mode: Preview\nflux_license_accepted: true\nai_setup_requested: [retired, flux]\n"
    )
    settings = load_settings(path)
    assert settings.pipeline_version == 3
    assert settings.quality_mode == "Quality"
    assert settings.ai_setup_requested == ["flux"]
    assert settings.flux_license_accepted
    assert settings.creative_resolution == 1536
    assert not hasattr(settings, "edit_budget_seconds")


def test_invalid_settings_shape_has_safe_defaults(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("- invalid\n- shape\n")
    settings = load_settings(path)
    assert settings.quality_mode == "Quality"
    assert not hasattr(settings, "edit_budget_seconds")
