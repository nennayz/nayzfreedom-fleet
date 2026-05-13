from __future__ import annotations
import json
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob, QAResult


class NoraAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        job.qa_result = QAResult(passed=True)
        job.stage = "nora_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Nora, QA editor for {job.pm.page_name}. "
            f"Brand tone: {job.pm.brand.tone}. "
            f"Audience: {job.pm.brand.target_audience}. "
            "Be strict. Reject weak hooks, off-brand visuals, and anything that feels generic."
        )
        from models.content_job import Script
        b = job.bella_output
        if isinstance(b, Script):
            content_summary = f"Script hook: {b.hook}\nScript body: {b.body}\nCTA: {b.cta}"
        else:
            content_summary = f"Content: {b}"
        user = (
            f"{content_summary}\n"
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
