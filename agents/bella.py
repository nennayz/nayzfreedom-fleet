from __future__ import annotations
import json
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, Script

_DRY_RUN_SCRIPT = Script(
    hook="wait— you've been doing your lips WRONG this whole time",
    body="step 1: exfoliate. step 2: liner ALL the way around. "
         "step 3: the trick nobody tells you— blot with tissue, dust translucent powder, reapply. "
         "your lips will literally last 8 hours.",
    cta="save this for your next glam sesh bestie",
    duration_seconds=30,
)


def _write_script_file(job: ContentJob) -> None:
    out_dir = Path("output") / job.pm.page_name / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    s = job.script
    (out_dir / "script.md").write_text(
        f"# Script\n\n**Hook:** {s.hook}\n\n**Body:** {s.body}\n\n**CTA:** {s.cta}\n\n_Duration: {s.duration_seconds}s_"
    )


class BellaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.script = _DRY_RUN_SCRIPT
        job.stage = "bella_done"
        _write_script_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        idea = job.selected_idea
        system = (
            TEAM_IDENTITY +
            f"You are Bella, a script writer for {job.pm.page_name}. "
            f"Script style: {job.pm.brand.script_style}. "
            f"Tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Write Reels scripts with Hook → Body → CTA structure."
        )
        user = (
            f"Brief: {job.brief}\nIdea: {idea.title}\nHook line: {idea.hook}\nAngle: {idea.angle}\n"
            f"Platforms: {', '.join(job.platforms)}\n\n"
            "Write a 15-60 second Reels script. Return JSON with keys: "
            "hook (str), body (str), cta (str), duration_seconds (int). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=1024)
        job.script = Script(**self._parse_json(raw))
        job.stage = "bella_done"
        _write_script_file(job)
        return job
