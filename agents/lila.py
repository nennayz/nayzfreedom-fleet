from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, ContentType, Script, ImageCaption, InfographicContent

_DRY_RUN_PROMPTS = {
    ContentType.VIDEO: (
        "Cinematic close-up of a gold-cased lipstick on ivory marble surface, "
        "soft natural morning light, minimalist Quiet Luxury aesthetic, "
        "white and cream tones, high-end editorial style"
    ),
    ContentType.IMAGE: (
        "Flat-lay of luxury beauty essentials on cream linen, gold accents, "
        "soft diffused light, editorial minimalist style"
    ),
    ContentType.INFOGRAPHIC: (
        "Clean white infographic layout with gold typography, step-by-step icons, "
        "minimalist beauty aesthetic, sans-serif font"
    ),
}
_DRY_RUN_IMAGE = "assets/placeholder.png"


class LilaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type == ContentType.ARTICLE:
            job.stage = "lila_done"
            return job
        job.visual_prompt = _DRY_RUN_PROMPTS.get(
            job.content_type,
            _DRY_RUN_PROMPTS[ContentType.VIDEO],
        )
        job.image_path = _DRY_RUN_IMAGE
        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        if job.content_type == ContentType.ARTICLE:
            job.stage = "lila_done"
            return job

        system = (
            TEAM_IDENTITY +
            f"You are Lila, visual director for {job.pm.page_name}. "
            f"Visual style: {job.pm.brand.visual.style}. "
            f"Color palette: {', '.join(job.pm.brand.visual.colors)}."
        )

        bella = job.bella_output
        if job.content_type == ContentType.VIDEO:
            hook_text = bella.hook if isinstance(bella, Script) else str(bella)
            user = (
                f"Script hook: {hook_text}\nBrief: {job.brief}\n"
                "Write a single cinematic image generation prompt for this Reel's key visual. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = None
        elif job.content_type == ContentType.IMAGE:
            caption_text = bella.caption if isinstance(bella, ImageCaption) else str(bella)
            user = (
                f"Caption: {caption_text}\nBrief: {job.brief}\n"
                "Write a single cinematic image generation prompt for this social media image. "
                "Be specific about lighting, composition, and mood. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = self._generate_image(job)
        elif job.content_type == ContentType.INFOGRAPHIC:
            points_text = "; ".join(bella.points) if isinstance(bella, InfographicContent) else str(bella)
            user = (
                f"Infographic points: {points_text}\nBrief: {job.brief}\n"
                "Write a single image generation prompt for this infographic's visual layout. "
                "Describe the layout, typography style, and color palette. Plain text only."
            )
            job.visual_prompt = self._call_claude(system, user, max_tokens=256)
            job.image_path = self._generate_image(job)

        job.stage = "lila_done"
        self._write_prompt_file(job)
        return job

    def _write_prompt_file(self, job: ContentJob) -> None:
        if job.visual_prompt is None:
            return
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "visual_prompt.txt").write_text(job.visual_prompt)

    def _generate_image(self, job: ContentJob) -> str:
        # Phase 2: wire GPT Image 2 here
        raise NotImplementedError("Image generation wired in Phase 2")
