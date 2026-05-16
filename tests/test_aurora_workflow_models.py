from datetime import date

import pytest
from pydantic import ValidationError

from models.aurora_workflow import (
    CalendarSlate,
    CrossTeamRequest,
    DailyMinimum,
    MissionType,
    PerformanceBucket,
    PerformanceReview,
    ProductionTicket,
    ProductionTicketType,
    RequestStatus,
    StoryboardScene,
    VideoPackageScene,
    VideoProductionPackage,
)
from models.content_job import ContentType


def _ticket(ticket_id: str, ticket_type: ProductionTicketType) -> ProductionTicket:
    content_type = {
        ProductionTicketType.ARTICLE: ContentType.ARTICLE,
        ProductionTicketType.INFOGRAPHIC: ContentType.INFOGRAPHIC,
        ProductionTicketType.SHORT_VIDEO: ContentType.VIDEO,
        ProductionTicketType.LONG_VIDEO: ContentType.VIDEO,
    }.get(ticket_type, ContentType.ARTICLE)
    storyboard = []
    if ticket_type == ProductionTicketType.LONG_VIDEO:
        storyboard = [
            StoryboardScene(
                number=1,
                duration_seconds=8,
                purpose="hook",
                visual_direction="Sloane meets the hero object",
                tool_hint="veo3",
            )
        ]
    return ProductionTicket(
        ticket_id=ticket_id,
        project="slay_hack",
        page_name="Slay Hack",
        ticket_type=ticket_type,
        content_type=content_type,
        title=f"{ticket_type.value} idea",
        objective="reach",
        owner="Slay",
        storyboard=storyboard,
    )


def test_mission_type_values_match_aurora_v2_spec():
    assert MissionType.NEW_PROJECT_DISCOVERY == "new_project_discovery"
    assert MissionType.CONTENT_CALENDAR_PLAN == "content_calendar_plan"
    assert MissionType.PRODUCTION_BATCH == "production_batch"
    assert MissionType.PERFORMANCE_REVIEW == "performance_review"


def test_daily_minimum_defaults_to_requested_output_floor():
    minimum = DailyMinimum()
    assert minimum.articles == 2
    assert minimum.infographics == 2
    assert minimum.short_videos == 1
    assert minimum.long_videos == 1
    assert minimum.short_video_duration_seconds == (15, 40)
    assert minimum.long_video_duration_seconds == (60, 180)


def test_long_video_ticket_requires_storyboard():
    with pytest.raises(ValidationError, match="long_video tickets require"):
        ProductionTicket(
            ticket_id="long-1",
            project="slay_hack",
            page_name="Slay Hack",
            ticket_type=ProductionTicketType.LONG_VIDEO,
            content_type=ContentType.VIDEO,
            title="Long video",
            objective="retention",
            owner="Video Producer",
        )


def test_video_package_requires_forward_scene_timing():
    with pytest.raises(ValidationError, match="end_second must be greater"):
        VideoPackageScene(
            number=1,
            start_second=10,
            end_second=10,
            purpose="hook",
            visual_direction="Static opening",
            prompt="Open with a static frame.",
        )


def test_video_package_records_scene_prompts_and_handoffs():
    package = VideoProductionPackage(
        ticket_id="saturday-long-video",
        title="Compilation-ready short-form episode",
        owner="Video Producer",
        platform_primary="youtube",
        format_name="Veo3 storyboard package",
        total_duration_seconds=16,
        scenes=[
            VideoPackageScene(
                number=1,
                start_second=0,
                end_second=8,
                purpose="hook",
                visual_direction="Sloane sees the hero object",
                prompt="Open with Sloane seeing the hero object.",
            ),
            VideoPackageScene(
                number=2,
                start_second=8,
                end_second=16,
                purpose="payoff",
                visual_direction="The routine resolves cleanly",
                prompt="Resolve the routine with a clean loop.",
            ),
        ],
        prompt_package=["Open with Sloane seeing the hero object."],
        asset_checklist=["Hero object reference"],
        handoff_notes=["Bella confirms the CTA."],
    )

    assert package.total_duration_seconds == 16
    assert package.scenes[0].start_second == 0
    assert package.scenes[1].end_second == 16
    assert package.prompt_package
    assert package.handoff_notes == ["Bella confirms the CTA."]


def test_ticket_primary_platform_must_be_listed():
    with pytest.raises(ValidationError, match="platform_primary must be one of platforms"):
        ProductionTicket(
            ticket_id="short-1",
            project="slay_hack",
            page_name="Slay Hack",
            ticket_type=ProductionTicketType.SHORT_VIDEO,
            content_type=ContentType.VIDEO,
            title="Short video",
            objective="reach",
            owner="Video Producer",
            platforms=["instagram"],
            platform_primary="tiktok",
        )


def test_ticket_records_decision_owner_and_workflow_controls():
    ticket = ProductionTicket(
        ticket_id="short-2",
        project="slay_hack",
        page_name="Slay Hack",
        ticket_type=ProductionTicketType.SHORT_VIDEO,
        content_type=ContentType.VIDEO,
        title="Short video",
        objective="reach",
        owner="Video Producer",
        decision_owner="Slay",
        priority=2,
        platforms=["tiktok", "instagram"],
        platform_primary="tiktok",
        acceptance_criteria=["Hook, payoff, CTA, and primary platform are clear."],
        evidence_links=["signal:beauty-hook-001"],
        asset_requirements=["Hero object reference"],
        linked_lessons=["lesson:short-hook-retention"],
    )

    assert ticket.decision_owner == "Slay"
    assert ticket.priority == 2
    assert ticket.platform_primary == "tiktok"
    assert ticket.acceptance_criteria
    assert ticket.asset_requirements == ["Hero object reference"]


def test_calendar_slate_counts_and_daily_minimum():
    slate = CalendarSlate(
        project="slay_hack",
        page_name="Slay Hack",
        pm_name="Slay",
        slate_date=date(2026, 5, 16),
        tickets=[
            _ticket("article-1", ProductionTicketType.ARTICLE),
            _ticket("article-2", ProductionTicketType.ARTICLE),
            _ticket("info-1", ProductionTicketType.INFOGRAPHIC),
            _ticket("info-2", ProductionTicketType.INFOGRAPHIC),
            _ticket("short-1", ProductionTicketType.SHORT_VIDEO),
            _ticket("long-1", ProductionTicketType.LONG_VIDEO),
        ],
    )

    counts = slate.counts_by_type()

    assert counts[ProductionTicketType.ARTICLE] == 2
    assert counts[ProductionTicketType.INFOGRAPHIC] == 2
    assert slate.satisfies_daily_minimum()


def test_calendar_slate_detects_missing_required_output():
    slate = CalendarSlate(
        project="slay_hack",
        page_name="Slay Hack",
        pm_name="Slay",
        slate_date=date(2026, 5, 16),
        tickets=[_ticket("article-1", ProductionTicketType.ARTICLE)],
    )
    assert not slate.satisfies_daily_minimum()


def test_performance_review_bucket_records_next_action():
    review = PerformanceReview(
        ticket_id="short-1",
        project="slay_hack",
        platform="tiktok",
        bucket=PerformanceBucket.SCALE,
        summary="High retention and comment rate.",
        metrics={"views": 250000, "shares": 4300},
        recommended_next_action="Make a sequel with the same hero object.",
    )
    assert review.bucket == PerformanceBucket.SCALE
    assert review.metrics["views"] == 250000


def test_cross_team_request_defaults_open():
    request = CrossTeamRequest(
        request_id="req-1",
        project="slay_hack",
        from_role="Lila",
        to_role="Bella",
        question="Can you make the hook more visual?",
    )
    assert request.status == RequestStatus.OPEN
