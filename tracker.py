from __future__ import annotations
import logging
from datetime import datetime, timezone
import requests
from config import Config
from models.content_job import ContentJob, PostPerformance

_META_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_TIKTOK_BASE = "https://open.tiktokapis.com/v2"
_TIKTOK_MATCH_WINDOW = 3600

logger = logging.getLogger(__name__)


def track_job(job: ContentJob, config: Config) -> ContentJob:
    if not job.publish_result:
        return job
    for platform, result in job.publish_result.items():
        if result.get("status") != "published":
            continue
        try:
            perf = _fetch_platform_metrics(platform, result, job, config)
            if perf:
                job.performance.append(perf)
        except Exception as e:
            logger.warning("Could not fetch metrics for %s: %s", platform, e)
    return job


def _fetch_platform_metrics(
    platform: str, result: dict, job: ContentJob, config: Config
) -> PostPerformance | None:
    if platform == "facebook":
        return _fetch_facebook(result["id"], config)
    if platform == "instagram":
        return _fetch_instagram(result["id"], config)
    if platform == "tiktok":
        return _fetch_tiktok(result, job, config)
    return None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fetch_facebook(post_id: str, config: Config) -> PostPerformance:
    resp = requests.get(
        f"{_META_GRAPH_BASE}/{post_id}",
        params={"fields": "likes.summary(true),shares,insights.metric(post_impressions_unique)"},
        headers=_auth_headers(config.meta_access_token),
    )
    resp.raise_for_status()
    data = resp.json()
    likes = data.get("likes", {}).get("summary", {}).get("total_count")
    shares = data.get("shares", {}).get("count")
    reach = None
    insights = data.get("insights", {}).get("data", [])
    if insights:
        values = insights[0].get("values", [])
        if values:
            reach = values[0].get("value")
    return PostPerformance(
        platform="facebook",
        likes=likes,
        reach=reach,
        shares=shares,
        recorded_at=datetime.now(timezone.utc),
    )


def _fetch_instagram(media_id: str, config: Config) -> PostPerformance:
    resp = requests.get(
        f"{_META_GRAPH_BASE}/{media_id}",
        params={"fields": "like_count,reach,saved"},
        headers=_auth_headers(config.meta_access_token),
    )
    resp.raise_for_status()
    data = resp.json()
    return PostPerformance(
        platform="instagram",
        likes=data.get("like_count"),
        reach=data.get("reach"),
        saves=data.get("saved"),
        recorded_at=datetime.now(timezone.utc),
    )


def _fetch_tiktok(result: dict, job: ContentJob, config: Config) -> PostPerformance | None:
    raise NotImplementedError("_fetch_tiktok not yet implemented")


def _job_publish_time(job: ContentJob) -> int:
    try:
        dt = datetime.strptime(job.id, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return int(datetime.now(timezone.utc).timestamp())
