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
from agents.publish import PublishAgent
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
2. run_zoe — generate ideas (each idea has a content_type)
3. request_checkpoint (stage: "idea_selection") — show ideas, wait for user to pick one
4. run_bella — write content for the selected idea based on its content_type
5. After Bella completes, check job.content_type:
   - video, image, or infographic → run_lila (visual direction)
   - article → skip run_lila entirely, go directly to step 6
6. request_checkpoint (stage: "content_review") — show content and visual (if applicable) for approval
7. run_nora — QA review. If QA fails and retry count < max_retries, re-run the relevant agent.
8. request_checkpoint (stage: "qa_review") — show QA result
9. run_roxy — hashtags + caption + timing + editorial guidance
10. run_emma — community FAQ
11. request_checkpoint (stage: "final_approval") — final sign-off before publishing
12. run_publish — publish to Meta (Facebook + Instagram). Pass schedule=true to post at Roxy's recommended time.

Never skip a checkpoint. After run_publish completes, declare the job complete.
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
            "publish": PublishAgent(config),
        }

    def run(self, job: ContentJob, unattended: bool = False) -> ContentJob:
        self._unattended = unattended
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
                stage=tool_input.get("stage"),
                summary=tool_input.get("summary"),
                options=tool_input.get("options", []),
                job=job,
                unattended=self._unattended,
            )
            if tool_input.get("stage") == "idea_selection" and job.ideas is not None:
                try:
                    decision_num = int(result.decision)
                    matched = next(
                        (i for i in job.ideas if i.number == decision_num), None
                    )
                    if matched is not None:
                        job.selected_idea = matched
                        job.content_type = matched.content_type
                except ValueError:
                    pass  # non-numeric input — leave selected_idea and content_type as-is
            return {"decision": result.decision}

        agent_name = tool_name.replace("run_", "")
        if agent_name not in self.agents:
            return {"error": f"Unknown tool: {tool_name}"}

        kwargs = {}
        if agent_name == "publish" and "schedule" in tool_input:
            kwargs["schedule"] = bool(tool_input["schedule"])
        self.agents[agent_name].run(job, **kwargs)
        return {"status": "ok", "stage": job.stage}
