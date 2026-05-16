from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator

from models.content_job import ContentType


class MissionType(str, Enum):
    NEW_PROJECT_DISCOVERY = "new_project_discovery"
    CONTENT_CALENDAR_PLAN = "content_calendar_plan"
    PRODUCTION_BATCH = "production_batch"
    PERFORMANCE_REVIEW = "performance_review"


class ProductionTicketType(str, Enum):
    ARTICLE = "article"
    INFOGRAPHIC = "infographic"
    SHORT_VIDEO = "short_video"
    LONG_VIDEO = "long_video"
    COMMUNITY_POST = "community_post"
    DISTRIBUTION_PACK = "distribution_pack"


class TicketStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    QA_REVIEW = "qa_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    LEARNED = "learned"


class PerformanceBucket(str, Enum):
    SCALE = "scale"
    REPAIR = "repair"
    LESSON_LEARNED = "lesson_learned"


class RequestStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    BLOCKED = "blocked"
    RESOLVED = "resolved"


class DailyMinimum(BaseModel):
    articles: int = Field(default=2, ge=0)
    infographics: int = Field(default=2, ge=0)
    short_videos: int = Field(default=1, ge=0)
    long_videos: int = Field(default=1, ge=0)
    short_video_duration_seconds: tuple[int, int] = (15, 40)
    long_video_duration_seconds: tuple[int, int] = (60, 180)


class StoryboardScene(BaseModel):
    number: int = Field(ge=1)
    duration_seconds: int = Field(default=8, gt=0)
    purpose: str
    visual_direction: str
    speaker: Optional[str] = None
    dialogue: Optional[str] = None
    tool_hint: Optional[str] = None


class ProductionTicket(BaseModel):
    ticket_id: str
    project: str
    page_name: str
    ticket_type: ProductionTicketType
    content_type: ContentType
    title: str
    objective: str
    owner: str
    decision_owner: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    platforms: list[str] = Field(default_factory=list)
    platform_primary: Optional[str] = None
    status: TicketStatus = TicketStatus.PLANNED
    due_date: Optional[date] = None
    brief: str = ""
    format_name: Optional[str] = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    asset_requirements: list[str] = Field(default_factory=list)
    asset_sources: list[str] = Field(default_factory=list)
    linked_lessons: list[str] = Field(default_factory=list)
    storyboard: list[StoryboardScene] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    qa_notes: list[str] = Field(default_factory=list)
    blocked_by_request_id: Optional[str] = None

    @model_validator(mode="after")
    def require_storyboard_for_long_video(self) -> "ProductionTicket":
        if self.ticket_type == ProductionTicketType.LONG_VIDEO and not self.storyboard:
            raise ValueError("long_video tickets require at least one storyboard scene")
        if self.platform_primary and self.platform_primary not in self.platforms:
            raise ValueError("platform_primary must be one of platforms")
        return self


class CalendarSlate(BaseModel):
    project: str
    page_name: str
    pm_name: str
    slate_date: date
    minimum: DailyMinimum = Field(default_factory=DailyMinimum)
    tickets: list[ProductionTicket] = Field(default_factory=list)
    notes: str = ""

    def counts_by_type(self) -> dict[ProductionTicketType, int]:
        counts = {ticket_type: 0 for ticket_type in ProductionTicketType}
        for ticket in self.tickets:
            counts[ticket.ticket_type] += 1
        return counts

    def satisfies_daily_minimum(self) -> bool:
        counts = self.counts_by_type()
        return (
            counts[ProductionTicketType.ARTICLE] >= self.minimum.articles
            and counts[ProductionTicketType.INFOGRAPHIC] >= self.minimum.infographics
            and counts[ProductionTicketType.SHORT_VIDEO] >= self.minimum.short_videos
            and counts[ProductionTicketType.LONG_VIDEO] >= self.minimum.long_videos
        )


class PerformanceReview(BaseModel):
    ticket_id: str
    project: str
    platform: str
    reviewed_at: datetime = Field(default_factory=datetime.now)
    bucket: PerformanceBucket
    summary: str
    metrics: dict[str, Union[float, int, str]] = Field(default_factory=dict)
    recommended_next_action: str


class LessonLearned(BaseModel):
    project: str
    page_name: str
    source_ticket_id: str
    lesson: str
    avoid_repeating: bool = False
    winning_pattern: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class CrossTeamRequest(BaseModel):
    request_id: str
    project: str
    from_role: str
    to_role: str
    question: str
    status: RequestStatus = RequestStatus.OPEN
    related_ticket_id: Optional[str] = None
    answer: Optional[str] = None
