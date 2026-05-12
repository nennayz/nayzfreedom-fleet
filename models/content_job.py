from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class VisualIdentity(BaseModel):
    colors: list[str]
    style: str


class BrandProfile(BaseModel):
    mission: str
    visual: VisualIdentity
    platforms: list[str]
    tone: str
    target_audience: str
    script_style: str
    nora_max_retries: int = 2


class PMProfile(BaseModel):
    page_name: str
    persona: str
    brand: BrandProfile


class Idea(BaseModel):
    number: int
    title: str
    hook: str
    angle: str


class Script(BaseModel):
    hook: str
    body: str
    cta: str
    duration_seconds: int


class QAResult(BaseModel):
    passed: bool
    script_feedback: Optional[str] = None
    visual_feedback: Optional[str] = None
    send_back_to: Optional[Literal["bella", "lila"]] = None


class GrowthStrategy(BaseModel):
    hashtags: list[str]
    caption: str
    best_post_time_utc: str
    best_post_time_thai: str


class CheckpointDecision(BaseModel):
    stage: str
    decision: str
    timestamp: datetime = Field(default_factory=datetime.now)


class PostPerformance(BaseModel):
    platform: str
    likes: Optional[int] = None
    reach: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    recorded_at: Optional[datetime] = None


class ContentJob(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    project: str
    pm: PMProfile
    brief: str
    platforms: list[str]
    stage: str = "init"
    status: JobStatus = JobStatus.PENDING
    dry_run: bool = False
    trend_data: Optional[dict] = None
    ideas: Optional[list[Idea]] = None
    selected_idea: Optional[Idea] = None
    script: Optional[Script] = None
    visual_prompt: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    qa_result: Optional[QAResult] = None
    nora_retry_count: int = 0
    growth_strategy: Optional[GrowthStrategy] = None
    community_faq_path: Optional[str] = None
    publish_result: Optional[dict] = None
    checkpoint_log: list[CheckpointDecision] = Field(default_factory=list)
    performance: list[PostPerformance] = Field(default_factory=list)
