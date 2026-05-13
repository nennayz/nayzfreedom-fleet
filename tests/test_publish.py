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


def test_publish_live_fb_image_calls_photos_endpoint(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "post-1"}
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook"]
    job = agent.run(job)
    assert mock_post.called
    call_url = mock_post.call_args[0][0]
    assert "page-123/photos" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_video_calls_videos_endpoint(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "vid-1"}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook"]
    job = agent.run(job)
    call_url = mock_post.call_args[0][0]
    assert "page-123/videos" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_article_calls_feed_endpoint(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "feed-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook"]
    job = agent.run(job)
    call_url = mock_post.call_args[0][0]
    assert "page-123/feed" in call_url
    assert job.publish_result["facebook"]["status"] == "published"


def test_publish_live_fb_schedule_flag_sends_scheduled_time(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "post-sched"}
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook"]
    job = agent.run(job, schedule=True)
    assert "scheduled_publish_time" in str(mock_post.call_args)
    assert job.publish_result["facebook"]["status"] == "scheduled"


def test_publish_live_ig_image_creates_container_then_publishes(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    container_resp = mocker.MagicMock()
    container_resp.raise_for_status = mocker.MagicMock()
    container_resp.json.return_value = {"id": "container-1"}
    publish_resp = mocker.MagicMock()
    publish_resp.raise_for_status = mocker.MagicMock()
    publish_resp.json.return_value = {"id": "ig-post-1"}
    mock_post.side_effect = [container_resp, publish_resp]
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["instagram"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    container_url = mock_post.call_args_list[0][0][0]
    publish_url = mock_post.call_args_list[1][0][0]
    assert "ig-456/media" in container_url
    assert "ig-456/media_publish" in publish_url
    assert job.publish_result["instagram"]["status"] == "published"


def test_publish_live_ig_reels_uses_resumable_upload(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4")
    mock_post = mocker.patch("agents.publish.requests.post")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {"id": "container-2", "uri": "https://rupload.facebook.com/upload-123"}
    upload_resp = mocker.MagicMock()
    upload_resp.raise_for_status = mocker.MagicMock()
    upload_resp.json.return_value = {"success": True}
    publish_resp = mocker.MagicMock()
    publish_resp.raise_for_status = mocker.MagicMock()
    publish_resp.json.return_value = {"id": "reel-1"}
    mock_post.side_effect = [init_resp, upload_resp, publish_resp]
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["instagram"]
    job = agent.run(job)
    assert mock_post.call_count == 3
    init_url = mock_post.call_args_list[0][0][0]
    upload_url = mock_post.call_args_list[1][0][0]
    publish_url = mock_post.call_args_list[2][0][0]
    assert "ig-456/media" in init_url
    assert "rupload.facebook.com" in upload_url
    assert "ig-456/media_publish" in publish_url
    assert job.publish_result["instagram"]["status"] == "published"
