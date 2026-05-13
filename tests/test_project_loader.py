import pytest
from project_loader import load_project, ProjectNotFoundError, load_platform_specs
from models.content_job import PMProfile, ContentType


def test_load_slay_hack():
    pm = load_project("slay_hack")
    assert isinstance(pm, PMProfile)
    assert pm.name == "Slay"
    assert pm.page_name == "Slay Hack"
    assert "Quiet Luxury" in pm.persona
    assert pm.brand.nora_max_retries == 2
    assert "#D4AF37" in pm.brand.visual.colors


def test_load_missing_project_raises():
    with pytest.raises(ProjectNotFoundError, match="nonexistent"):
        load_project("nonexistent")

def test_load_slay_hack_allowed_content_types():
    pm = load_project("slay_hack")
    assert set(pm.brand.allowed_content_types) == {
        ContentType.VIDEO, ContentType.ARTICLE,
        ContentType.IMAGE, ContentType.INFOGRAPHIC,
    }

def test_load_platform_specs_slay_hack():
    specs = load_platform_specs("slay_hack")
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
