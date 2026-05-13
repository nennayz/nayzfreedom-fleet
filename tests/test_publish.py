from agents.publish import PublishAgent
from config import Config
from models.content_job import ContentType, ImageCaption, Article, Script, GrowthStrategy


def make_publish_config():
    return Config(
        anthropic_api_key="test",
        brave_search_api_key="brave",
        openai_api_key="oai",
        meta_access_token="meta-token",
        meta_page_id="page-123",
        meta_ig_user_id="ig-456",
    )


def _make_growth_strategy():
    return GrowthStrategy(
        hashtags=["#glam"],
        caption="look of the day",
        best_post_time_utc="13:00",
        best_post_time_thai="20:00",
    )


def make_image_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.IMAGE)
    job.bella_output = ImageCaption(caption="Soft glam look", alt_text="Woman in gold")
    job.visual_prompt = "Gold lipstick on marble"
    job.image_path = "assets/placeholder.png"
    job.growth_strategy = _make_growth_strategy()
    return job


def make_video_job(dry_run=True, video_path=None):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.VIDEO)
    job.bella_output = Script(hook="h", body="b", cta="c", duration_seconds=30)
    job.visual_prompt = "Cinematic gold close-up"
    job.video_path = video_path
    job.growth_strategy = _make_growth_strategy()
    return job


def make_article_job(dry_run=True):
    from tests.test_bella import make_job_with_idea
    job = make_job_with_idea(dry_run=dry_run, content_type=ContentType.ARTICLE)
    job.bella_output = Article(heading="The Look", body="Step 1...", cta="Shop now")
    job.growth_strategy = _make_growth_strategy()
    return job


def test_publish_dry_run_sets_result():
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=True)
    job = agent.run(job)
    assert job.publish_result == {"dry_run": True, "platforms": job.platforms}
    assert job.stage == "publish_done"
