from models.content_job import (
    ContentJob, PMProfile, BrandProfile, VisualIdentity,
    Idea, Script, QAResult, GrowthStrategy, CheckpointDecision,
    PostPerformance, JobStatus
)

def make_brand():
    return BrandProfile(
        mission="Test mission",
        visual=VisualIdentity(colors=["#FFF"], style="minimalist"),
        platforms=["instagram"],
        tone="casual",
        target_audience="Gen Z women USA",
        script_style="lowercase slang",
        nora_max_retries=2,
    )

def make_pm():
    return PMProfile(name="Test", page_name="Test Page", persona="You are a test PM.", brand=make_brand())

def test_content_job_defaults():
    job = ContentJob(project="test", pm=make_pm(), brief="test brief", platforms=["instagram"])
    assert job.status == JobStatus.PENDING
    assert job.stage == "init"
    assert job.dry_run is False
    assert job.nora_retry_count == 0
    assert job.checkpoint_log == []
    assert job.performance == []

def test_content_job_id_is_timestamp_format():
    job = ContentJob(project="test", pm=make_pm(), brief="b", platforms=["instagram"])
    assert len(job.id) == 15  # YYYYMMDD_HHMMSS

def test_idea_model():
    idea = Idea(number=1, title="Test Idea", hook="Test hook", angle="Tutorial")
    assert idea.number == 1

def test_qa_result_defaults():
    qa = QAResult(passed=True)
    assert qa.send_back_to is None
    assert qa.script_feedback is None

def test_pm_profile_has_name():
    pm = PMProfile(name="Slay", page_name="Slay Hack", persona="test", brand=make_brand())
    assert pm.name == "Slay"
