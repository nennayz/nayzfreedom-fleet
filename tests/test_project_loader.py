import pytest
from project_loader import load_project, ProjectNotFoundError, load_platform_specs
from models.content_job import PMProfile, ContentType


def test_load_nayzfreedom_fleet():
    pm = load_project("nayzfreedom_fleet")
    assert isinstance(pm, PMProfile)
    assert pm.name == "Slay"
    assert pm.page_name == "NayzFreedom Fleet"
    assert "Quiet Luxury" in pm.persona
    assert pm.brand.nora_max_retries == 2
    assert "#D4AF37" in pm.brand.visual.colors


def test_load_missing_project_raises():
    with pytest.raises(ProjectNotFoundError, match="nonexistent"):
        load_project("nonexistent")


def test_load_legacy_slay_hack_alias():
    pm = load_project("slay_hack")
    assert pm.page_name == "NayzFreedom Fleet"


def test_load_nayzfreedom_fleet_allowed_content_types():
    pm = load_project("nayzfreedom_fleet")
    assert set(pm.brand.allowed_content_types) == {
        ContentType.VIDEO, ContentType.ARTICLE,
        ContentType.IMAGE, ContentType.INFOGRAPHIC,
    }

def test_load_platform_specs_nayzfreedom_fleet():
    specs = load_platform_specs("nayzfreedom_fleet")
    assert "instagram" in specs
    assert "facebook" in specs
    assert "tiktok" in specs
    assert "youtube" in specs
    assert len(specs["instagram"]) > 0

def test_load_platform_specs_missing_project_raises():
    with pytest.raises(ProjectNotFoundError):
        load_platform_specs("nonexistent")

def test_load_platform_specs_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project_dir = tmp_path / "projects" / "test_no_specs"
    project_dir.mkdir(parents=True)
    # No platform_specs.yaml — function should return {}
    result = load_platform_specs("test_no_specs")
    assert result == {}
