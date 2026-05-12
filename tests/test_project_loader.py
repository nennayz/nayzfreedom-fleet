import pytest
from project_loader import load_project, ProjectNotFoundError
from models.content_job import PMProfile


def test_load_slay_hack():
    pm = load_project("slay_hack")
    assert isinstance(pm, PMProfile)
    assert pm.name == "Slay"
    assert pm.page_name == "Slay Hack Agency"
    assert pm.brand.nora_max_retries == 2
    assert "#D4AF37" in pm.brand.visual.colors


def test_load_missing_project_raises():
    with pytest.raises(ProjectNotFoundError, match="nonexistent"):
        load_project("nonexistent")
