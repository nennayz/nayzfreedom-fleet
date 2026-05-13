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
        token = self.config.meta_access_token
        ig_user_id = self.config.meta_ig_user_id
        if job.content_type == ContentType.VIDEO:
            return self._post_ig_reel(job, caption, scheduled_time, token, ig_user_id)
        return self._post_ig_image(job, caption, scheduled_time, token, ig_user_id)

    def _post_ig_image(
        self,
        job: ContentJob,
        caption: str,
        scheduled_time: int | None,
        token: str,
        ig_user_id: str,
    ) -> dict:
        assert job.image_path is not None
        url = f"{_META_GRAPH_BASE}/{ig_user_id}/media"
        data: dict = {"caption": caption, "access_token": token}
        if scheduled_time:
            data["scheduled_publish_time"] = str(scheduled_time)
        with open(job.image_path, "rb") as f:
            resp = requests.post(url, data=data, files={"source": f})
        resp.raise_for_status()
        container_id = resp.json()["id"]
        pub_url = f"{_META_GRAPH_BASE}/{ig_user_id}/media_publish"
        pub_resp = requests.post(pub_url, data={"creation_id": container_id, "access_token": token})
        pub_resp.raise_for_status()
        return pub_resp.json()

    def _post_ig_reel(
        self,
        job: ContentJob,
        caption: str,
        scheduled_time: int | None,
        token: str,
        ig_user_id: str,
    ) -> dict:
        assert job.video_path is not None
        file_size = Path(job.video_path).stat().st_size
        url = f"{_META_GRAPH_BASE}/{ig_user_id}/media"
        init_data: dict = {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "access_token": token,
        }
        if scheduled_time:
            init_data["scheduled_publish_time"] = str(scheduled_time)
        init_resp = requests.post(
            url,
            data=init_data,
            headers={"file_size": str(file_size), "file_type": "video/mp4"},
        )
        init_resp.raise_for_status()
        init_json = init_resp.json()
        container_id = init_json["id"]
        upload_uri = init_json.get(
            "uri",
            f"https://rupload.facebook.com/video-upload/v19.0/{container_id}",
        )
        with open(job.video_path, "rb") as f:
            upload_resp = requests.post(
                upload_uri,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f,
            )
        upload_resp.raise_for_status()
        pub_url = f"{_META_GRAPH_BASE}/{ig_user_id}/media_publish"
        pub_resp = requests.post(pub_url, data={"creation_id": container_id, "access_token": token})
        pub_resp.raise_for_status()
        return pub_resp.json()
