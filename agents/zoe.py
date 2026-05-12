from __future__ import annotations
import json
from pathlib import Path
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, Idea

_DRY_RUN_IDEAS = [
    Idea(number=1, title="The Invisible Lip Liner Hack", hook="POV: your lips last all day", angle="Tutorial"),
    Idea(number=2, title="Quiet Luxury Morning Routine", hook="This is how rich girls start their day", angle="Lifestyle"),
    Idea(number=3, title="5 Dupes That Beat the Original", hook="Stop wasting money on expensive formulas", angle="Review"),
    Idea(number=4, title="The 3-Step Kiss-Proof Secret", hook="omg why did nobody tell me this earlier", angle="Tutorial"),
    Idea(number=5, title="Get Ready With Me: Date Night Edition", hook="come get ready with me for a night out", angle="GRWM"),
]


def _write_ideas_file(job: ContentJob) -> None:
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{i.number}. **{i.title}**\n   Hook: {i.hook}\n   Angle: {i.angle}" for i in job.ideas]
    (out_dir / "ideas.md").write_text("# Ideas\n\n" + "\n\n".join(lines))


class ZoeAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.ideas = _DRY_RUN_IDEAS
        job.stage = "zoe_done"
        _write_ideas_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        trends_str = json.dumps(job.trend_data, ensure_ascii=False)
        system = (
            f"You are Zoe, a content ideation specialist for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Target audience: {job.pm.brand.target_audience}."
        )
        user = (
            f"Brief: {job.brief}\nPlatforms: {', '.join(job.platforms)}\n"
            f"Trends: {trends_str}\n\n"
            "Generate 5-7 content ideas. Return a JSON array of objects with keys: "
            "number (int), title (str), hook (str, max 10 words), angle (str). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=1024)
        job.ideas = [Idea(**i) for i in json.loads(raw)]
        job.stage = "zoe_done"
        _write_ideas_file(job)
        return job
