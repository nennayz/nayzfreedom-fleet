from __future__ import annotations
import json
from agents.base_agent import BaseAgent
from models.content_job import ContentJob, QAResult


class NoraAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.qa_result = QAResult(passed=True)
        job.stage = "nora_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        user = (
            f"Script hook: {job.script.hook}\n"
            f"Script body: {job.script.body}\n"
            f"CTA: {job.script.cta}\n"
            f"Visual prompt: {job.visual_prompt}\n\n"
            "Review this content. Return JSON with keys: passed (bool), "
            "script_feedback (str or null), visual_feedback (str or null), "
            "send_back_to ('bella' | 'lila' | null). JSON only."
        )
        raw = self._call_claude(system, user, max_tokens=512)
        result = QAResult(**self._parse_json(raw))
        if not result.passed:
            job.nora_retry_count += 1
        job.qa_result = result
        job.stage = "nora_done"
        return job
