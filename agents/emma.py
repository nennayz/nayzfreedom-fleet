from __future__ import annotations
from pathlib import Path
from agents.base_agent import BaseAgent, TEAM_IDENTITY
from models.content_job import ContentJob

_DRY_RUN_FAQ = """# FAQ — Community Responses

**Q: What product are you using?**
A: it's actually a technique, not just a product! the tissue blot + powder method works with literally any lipstick ✨

**Q: Does this work with glossy formulas?**
A: yes bestie! the key is the powder step — it sets the gloss so it won't budge

**Q: How long does it actually last?**
A: tested it for 8 hours straight — eating, drinking, everything. it held 💋
"""


class EmmaAgent(BaseAgent):
    def run_dry(self, job: ContentJob, **kwargs) -> ContentJob:
        faq_path = self._write_faq(job, _DRY_RUN_FAQ)
        job.community_faq_path = str(faq_path)
        job.stage = "emma_done"
        return job

    def run_live(self, job: ContentJob, **kwargs) -> ContentJob:
        system = (
            TEAM_IDENTITY +
            f"You are Emma, community manager for {job.pm.page_name}. "
            "Write warm, friendly, conversational responses. "
            f"Tone: {job.pm.brand.tone}."
        )
        user = (
            f"Brief: {job.brief}\nScript: {job.script.hook} — {job.script.body}\n\n"
            "Write a FAQ markdown with 3-5 likely comments and ideal responses. "
            "Use the brand's tone. Markdown only."
        )
        faq_content = self._call_claude(system, user, max_tokens=1024)
        faq_path = self._write_faq(job, faq_content)
        job.community_faq_path = str(faq_path)
        job.stage = "emma_done"
        return job

    def _write_faq(self, job: ContentJob, content: str) -> Path:
        out_dir = Path("output") / job.pm.page_name / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "faq.md"
        path.write_text(content)
        return path
