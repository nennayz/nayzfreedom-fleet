from __future__ import annotations
import json
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, GrowthStrategy
from project_loader import load_platform_specs

_DRY_RUN_STRATEGY = GrowthStrategy(
    hashtags=["#LongLastingLips","#GlossyLips","#LipHack","#QuietLuxury","#BeautyHacks","#GlowUp"],
    caption="the lip hack you didn't know you needed 💋 save this before your next glam sesh",
    best_post_time_utc="13:00",
    best_post_time_thai="20:00",
    editorial_guidance={
        "instagram": "Hook within 3 seconds. Caption under 150 chars. Hashtags in first comment.",
        "facebook": "Conversational tone. 1-3 sentences. Hashtags optional, inline.",
        "tiktok": "Text overlay on video. CTA in last 3 seconds. Sound-on assumed. Trending audio boosts reach.",
        "youtube": "Thumbnail-first mindset. Title under 60 chars. Description with timestamps. First 30 seconds must hook.",
    },
)


def _write_growth_file(job: ContentJob) -> None:
    g = job.growth_strategy
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "growth.md").write_text(
        f"# Growth Strategy\n\n**Caption:** {g.caption}\n\n"
        f"**Hashtags:** {' '.join(g.hashtags)}\n\n"
        f"**Best post time:** {g.best_post_time_utc} UTC / {g.best_post_time_thai} Thai"
    )


class RoxyAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.growth_strategy = _DRY_RUN_STRATEGY
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Roxy, growth strategist for {job.pm.page_name}. "
            f"Target audience: {job.pm.brand.target_audience}. "
            f"Platforms: {', '.join(job.platforms)}."
        )
        user = (
            f"Brief: {job.brief}\nScript hook: {job.script.hook}\n"
            "Provide 5-10 hashtags, a short caption, and optimal post times for USA audience. "
            "Return JSON with keys: hashtags (list of str), caption (str), "
            "best_post_time_utc (str HH:MM), best_post_time_thai (str HH:MM). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=512)
        job.growth_strategy = GrowthStrategy(**self._parse_json(raw))
        job.stage = "roxy_done"
        _write_growth_file(job)
        return job
