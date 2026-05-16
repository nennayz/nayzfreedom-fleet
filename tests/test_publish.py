from agents.publish import PublishAgent, has_publish_failures
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
        tiktok_access_token="tiktok-token",
        youtube_client_id="yt-client-id",
        youtube_client_secret="yt-client-secret",
        youtube_refresh_token="yt-refresh-token",
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


def test_has_publish_failures_detects_failed_platform():
    assert has_publish_failures({"facebook": {"status": "failed"}}) is True
    assert has_publish_failures({"facebook": {"status": "published"}}) is False
    assert has_publish_failures(None) is False


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


def test_publish_article_skips_instagram(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["instagram", "facebook"]
    job = agent.run(job)
    assert "instagram" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
    call_url = mock_post.call_args[0][0]
    assert "ig-456" not in call_url


def test_publish_partial_failure_records_per_platform(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    mock_post = mocker.patch("agents.publish.requests.post")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-ok"}
    mock_post.side_effect = [fb_resp, Exception("IG quota exceeded")]
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["facebook", "instagram"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["instagram"]["status"] == "failed"
    assert "IG quota exceeded" in job.publish_result["instagram"]["error"]
    assert job.stage == "publish_done"


def test_publish_missing_image_path_raises_value_error():
    import pytest
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = None
    with pytest.raises(ValueError, match=job.id):
        agent.run(job)


def test_publish_missing_media_file_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import pytest
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(tmp_path / "nonexistent.png")
    with pytest.raises(ValueError, match=job.id):
        agent.run(job)


def test_publish_tool_registered_in_agent_tools():
    from tools.agent_tools import get_tool_definitions
    names = [t["name"] for t in get_tool_definitions()]
    assert "run_publish" in names


def test_publish_agent_registered_in_orchestrator():
    from orchestrator import Orchestrator
    from config import Config
    cfg = Config(anthropic_api_key="k", brave_search_api_key="b", openai_api_key="o")
    orch = Orchestrator(cfg)
    assert "publish" in orch.agents


def test_main_publish_only_flag_dispatches_publish_agent(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from job_store import save_job

    job = make_image_job(dry_run=False)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    job.image_path = str(img_file)
    job.stage = "emma_done"
    save_job(job)

    mock_run = mocker.patch.object(PublishAgent, "run_live", return_value=job)
    mocker.patch("main.Config.from_env", return_value=make_publish_config())

    import sys
    sys.argv = ["main.py", "--publish-only", job.id]
    from main import main
    main()

    mock_run.assert_called_once()


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


def test_publish_tiktok_image_skips_with_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert job.publish_result["tiktok"]["status"] == "skipped"
    assert "public URL" in job.publish_result["tiktok"]["reason"]


def test_publish_tiktok_article_excluded_from_platforms(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook", "tiktok"]
    job = agent.run(job)
    assert "tiktok" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
    assert mock_post.call_count == 1
    assert "page-123/feed" in mock_post.call_args[0][0]


def test_publish_tiktok_video_init_upload_publish(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-1", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "PUBLISH_COMPLETE"}}
    mock_post.side_effect = [init_resp, status_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    init_url = mock_post.call_args_list[0][0][0]
    assert "video/init" in init_url
    assert mock_put.called
    assert job.publish_result["tiktok"]["status"] == "published"
    assert job.publish_result["tiktok"]["publish_id"] == "pub-1"


def test_publish_tiktok_video_poll_timeout(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    mocker.patch("agents.publish.time.sleep")
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-2", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "PROCESSING"}}
    mock_post.side_effect = [init_resp] + [status_resp] * 60
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["tiktok"]
    job = agent.run(job)
    assert job.publish_result["tiktok"]["status"] == "failed"
    assert "timed out" in job.publish_result["tiktok"]["error"]


def test_publish_tiktok_failure_does_not_affect_meta(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-vid-1"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.json.return_value = {
        "data": {"publish_id": "pub-3", "upload_url": "https://upload.tiktok.com/v1/upload"}
    }
    status_resp = mocker.MagicMock()
    status_resp.raise_for_status = mocker.MagicMock()
    status_resp.json.return_value = {"data": {"status": "FAILED", "fail_reason": "QUOTA_EXCEEDED"}}
    mock_post.side_effect = [fb_resp, init_resp, status_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook", "tiktok"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["tiktok"]["status"] == "failed"
    assert "QUOTA_EXCEEDED" in job.publish_result["tiktok"]["error"]


def test_publish_youtube_image_skips_with_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"PNG")
    agent = PublishAgent(make_publish_config())
    job = make_image_job(dry_run=False)
    job.image_path = str(img_file)
    job.platforms = ["youtube"]
    job = agent.run(job)
    assert job.publish_result["youtube"]["status"] == "skipped"
    assert "YouTube only supports video uploads" in job.publish_result["youtube"]["reason"]


def test_publish_youtube_article_excluded_from_platforms(mocker):
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_post.return_value.raise_for_status = mocker.MagicMock()
    mock_post.return_value.json.return_value = {"id": "fb-1"}
    agent = PublishAgent(make_publish_config())
    job = make_article_job(dry_run=False)
    job.platforms = ["facebook", "youtube"]
    job = agent.run(job)
    assert "youtube" not in job.publish_result
    assert job.publish_result["facebook"]["status"] == "published"
    assert mock_post.call_count == 1
    assert "page-123/feed" in mock_post.call_args_list[0][0][0]


def test_publish_youtube_video_upload(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.headers = {"Location": "https://upload.googleapis.com/v1/upload"}
    mock_post.side_effect = [auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    mock_put.return_value.json.return_value = {"id": "yt-1", "status": {"uploadStatus": "uploaded"}}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["youtube"]
    job = agent.run(job)
    assert mock_post.call_count == 2
    auth_url = mock_post.call_args_list[0][0][0]
    assert "oauth2.googleapis.com/token" in auth_url
    init_url = mock_post.call_args_list[1][0][0]
    assert "youtube/v3/videos" in init_url
    assert mock_put.called
    assert mock_put.call_args[1]["headers"]["Content-Type"] == "video/mp4"
    assert job.publish_result["youtube"]["status"] == "published"
    assert job.publish_result["youtube"]["id"] == "yt-1"


def test_publish_youtube_scheduled(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status = mocker.MagicMock()
    init_resp.headers = {"Location": "https://upload.googleapis.com/v1/upload"}
    mock_post.side_effect = [auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    mock_put.return_value.json.return_value = {"id": "yt-2", "status": {"uploadStatus": "uploaded"}}
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["youtube"]
    job = agent.run(job, schedule=True)
    init_body = mock_post.call_args_list[1][1]["json"]
    assert init_body["status"]["privacyStatus"] == "private"
    assert "publishAt" in init_body["status"]
    assert job.publish_result["youtube"]["status"] == "scheduled"


def test_publish_youtube_failure_does_not_affect_meta(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"MP4DATA")
    mock_post = mocker.patch("agents.publish.requests.post")
    mock_put = mocker.patch("agents.publish.requests.put")
    fb_resp = mocker.MagicMock()
    fb_resp.raise_for_status = mocker.MagicMock()
    fb_resp.json.return_value = {"id": "fb-vid-1"}
    auth_resp = mocker.MagicMock()
    auth_resp.raise_for_status = mocker.MagicMock()
    auth_resp.json.return_value = {"access_token": "yt-token"}
    init_resp = mocker.MagicMock()
    init_resp.raise_for_status.side_effect = Exception("QUOTA_EXCEEDED")
    mock_post.side_effect = [fb_resp, auth_resp, init_resp]
    mock_put.return_value.raise_for_status = mocker.MagicMock()
    agent = PublishAgent(make_publish_config())
    job = make_video_job(dry_run=False, video_path=str(vid_file))
    job.platforms = ["facebook", "youtube"]
    job = agent.run(job)
    assert job.publish_result["facebook"]["status"] == "published"
    assert job.publish_result["youtube"]["status"] == "failed"
    assert "QUOTA_EXCEEDED" in job.publish_result["youtube"]["error"]
