from __future__ import annotations
import requests
from pathlib import Path
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, ContentType

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"


class PublishAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.publish_result = {"dry_run": True, "platforms": job.platforms}
        job.stage = "publish_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        schedule: bool = kwargs.get("schedule", False)
        effective_platforms = [
            p for p in job.platforms
            if not (job.content_type == ContentType.ARTICLE and p == "instagram")
        ]
        if job.content_type != ContentType.ARTICLE:
            media_path = job.video_path if job.content_type == ContentType.VIDEO else job.image_path
            if not media_path:
                raise ValueError(
                    f"PublishAgent: no media file on job {job.id} "
                    f"(content_type={job.content_type})"
                )
            if not Path(media_path).exists():
                raise ValueError(
                    f"PublishAgent: media file not found: {media_path} (job {job.id})"
                )
        scheduled_time = self._scheduled_unix_ts(job) if schedule else None
        caption = self._build_caption(job)
        result: dict = {}
        for platform in effective_platforms:
            try:
                if platform == "facebook":
                    post_result = self._post_facebook(job, caption, scheduled_time)
                elif platform == "instagram":
                    post_result = self._post_instagram(job, caption, scheduled_time)
                else:
                    result[platform] = {"status": "skipped", "error": f"unsupported platform: {platform}"}
                    continue
                status = "scheduled" if scheduled_time else "published"
                result[platform] = {"status": status, **post_result}
            except Exception as e:
                result[platform] = {"status": "failed", "error": str(e)}
        job.publish_result = result
        job.stage = "publish_done"
        return job

    def _build_caption(self, job: ContentJob) -> str:
        if job.growth_strategy is None:
            return ""
        tags = " ".join(job.growth_strategy.hashtags)
        return f"{job.growth_strategy.caption}\n\n{tags}"

    def _scheduled_unix_ts(self, job: ContentJob) -> int | None:
        if job.growth_strategy is None:
            return None
        from datetime import datetime, timezone, timedelta
        try:
            hh, mm = job.growth_strategy.best_post_time_utc.split(":")
            now = datetime.now(timezone.utc)
            scheduled = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if scheduled <= now:
                scheduled += timedelta(days=1)
            return int(scheduled.timestamp())
        except Exception:
            return None

    def _post_facebook(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        token = self.config.meta_access_token
        page_id = self.config.meta_page_id
        if job.content_type == ContentType.ARTICLE:
            url = f"{_META_GRAPH_BASE}/{page_id}/feed"
            data: dict = {"message": caption, "access_token": token}
            if scheduled_time:
                data["scheduled_publish_time"] = str(scheduled_time)
                data["published"] = "false"
            resp = requests.post(url, data=data)
            resp.raise_for_status()
            return resp.json()
        media_path = job.image_path if job.content_type != ContentType.VIDEO else job.video_path
        assert media_path is not None
        if job.content_type == ContentType.VIDEO:
            url = f"{_META_GRAPH_BASE}/{page_id}/videos"
            caption_key = "description"
        else:
            url = f"{_META_GRAPH_BASE}/{page_id}/photos"
            caption_key = "caption"
        data = {caption_key: caption, "access_token": token}
        if scheduled_time:
            data["scheduled_publish_time"] = str(scheduled_time)
            data["published"] = "false"
        with open(media_path, "rb") as f:
            resp = requests.post(url, data=data, files={"source": f})
        resp.raise_for_status()
        return resp.json()

    def _post_instagram(self, job: ContentJob, caption: str, scheduled_time: int | None) -> dict:
        raise NotImplementedError
