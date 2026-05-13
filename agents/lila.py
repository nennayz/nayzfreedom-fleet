from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob

_DRY_RUN_PROMPT = (
    "Cinematic close-up of a gold-cased lipstick on ivory marble surface, "
    "soft natural morning light, minimalist Quiet Luxury aesthetic, "
    "white and cream tones, high-end editorial style"
)
_DRY_RUN_IMAGE = "assets/placeholder.png"


class LilaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.visual_prompt = _DRY_RUN_PROMPT
        job.image_path = _DRY_RUN_IMAGE
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Lila, visual director for {job.pm.page_name}. "
            f"Visual style: {job.pm.brand.visual.style}. "
            f"Color palette: {', '.join(job.pm.brand.visual.colors)}."
        )
        from models.content_job import Script
        hook_text = job.bella_output.hook if isinstance(job.bella_output, Script) else str(job.selected_idea.hook if job.selected_idea else job.brief)
        user = (
            f"Script hook: {hook_text}\nBrief: {job.brief}\n"
            "Write a single cinematic image generation prompt for this Reel's key visual. "
            "Be specific about lighting, composition, and mood. Plain text only."
        )
        job.visual_prompt = self._call_claude(system, user, max_tokens=256)
        job.image_path = self._generate_image(job)
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def _write_prompt_file(self, job: ContentJob) -> None:
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "visual_prompt.txt").write_text(job.visual_prompt or "")

    def _generate_image(self, job: ContentJob) -> str:
        # Phase 2: wire GPT Image 2 here
        raise NotImplementedError("Image generation wired in Phase 2")
