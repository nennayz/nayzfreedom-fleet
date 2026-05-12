from __future__ import annotations
import json
import anthropic
from agents.mia import MiaAgent
from agents.zoe import ZoeAgent
from agents.bella import BellaAgent
from agents.lila import LilaAgent
from agents.nora import NoraAgent
from agents.roxy import RoxyAgent
from agents.emma import EmmaAgent
from checkpoint import pause
from config import Config
from job_store import save_job, load_recent_performance
from models.content_job import ContentJob, JobStatus
from tools.agent_tools import get_tool_definitions

_ROBIN_SYSTEM = """You are Robin, Chief of Staff at NayzFreedom.

You act directly on behalf of the owner. Every decision you make optimizes for maximum business benefit — reach, engagement, and brand growth — not just task completion.

Before recommending strategy, review past job performance data provided in context. If no performance data exists, proceed without it.

You coordinate Freedom Architects (Mia, Zoe, Bella, Lila, Nora, Roxy, Emma) through {pm_name}, the PM for {page_name}.

## Team workflow (follow this order):
1. run_mia — research trends
2. run_zoe — generate ideas
3. request_checkpoint (stage: "idea_selection") — show ideas, wait for user to pick one
4. run_bella — write script for the selected idea
5. run_lila — create visual prompt and key image
6. request_checkpoint (stage: "content_review") — show script and visual for approval
7. run_nora — QA review. If QA fails and retry count < max_retries, re-run the relevant agent.
8. request_checkpoint (stage: "qa_review") — show QA result
9. run_roxy — hashtags + caption + timing
10. run_emma — community FAQ
11. request_checkpoint (stage: "final_approval") — final sign-off before publishing

Never skip a checkpoint. After final_approval, declare the job complete.
"""


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.agents = {
            "mia": MiaAgent(config),
            "zoe": ZoeAgent(config),
            "bella": BellaAgent(config),
            "lila": LilaAgent(config),
            "nora": NoraAgent(config),
            "roxy": RoxyAgent(config),
            "emma": EmmaAgent(config),
        }

    def run(self, job: ContentJob) -> ContentJob:
        job.status = JobStatus.RUNNING
        system_prompt = _ROBIN_SYSTEM.format(
            pm_name=job.pm.name,
            page_name=job.pm.page_name,
        )
        perf_summary = load_recent_performance(job.pm.page_name)
        first_message = f"Brief: {job.brief}\nPlatforms: {', '.join(job.platforms)}"
        if perf_summary:
            first_message = f"{perf_summary}\n\n{first_message}"
        messages: list[dict] = [{"role": "user", "content": first_message}]

        while True:
            response = self.client.messages.create(
                model="claude-opus-4-7",
                max_tokens=4096,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                tools=get_tool_definitions(),
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                job.status = JobStatus.COMPLETED
                save_job(job)
                return job

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._dispatch(block.name, block.input, job)
                save_job(job)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    def _dispatch(self, tool_name: str, tool_input: dict, job: ContentJob) -> dict:
        if tool_name == "request_checkpoint":
            result = pause(
                stage=tool_input["stage"],
                summary=tool_input["summary"],
                options=tool_input.get("options", []),
                job=job,
            )
            return {"decision": result.decision}

        agent_name = tool_name.replace("run_", "")
        if agent_name not in self.agents:
            return {"error": f"Unknown tool: {tool_name}"}

        self.agents[agent_name].run(job)
        return {"status": "ok", "stage": job.stage}
