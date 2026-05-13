import pytest
from project_loader import load_project, ProjectNotFoundError
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
