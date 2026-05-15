from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewMember:
    slug: str
    name: str
    image: str
    ship_role: str
    operational_role: str
    station: str
    workflow_stage: str
    mission_phase: str
    summary: str
    personality: str
    strengths: list[str]
    watch_outs: list[str]
    inputs: list[str]
    outputs: list[str]
    visual_signature: str
    accent_color: str
    quote: str


CREW = (
    CrewMember(
        slug="robin",
        name="Robin",
        image="/static/crew/robin.png",
        ship_role="Chief Officer",
        operational_role="Orchestrator",
        station="Captain's Bridge",
        workflow_stage="Mission command",
        mission_phase="0. Command",
        summary="Keeps The Aurora aligned and turns briefs into action.",
        personality="calm, strategic, decisive",
        strengths=["coordination", "prioritization", "decision framing"],
        watch_outs=["can optimize for throughput before artistry"],
        inputs=["captain brief", "project context", "performance history"],
        outputs=["mission route", "crew dispatch", "final coordination"],
        visual_signature="command coat, emerald-gold accents, composed bridge posture",
        accent_color="#2f9b83",
        quote="A good voyage is won before the sails rise.",
    ),
    CrewMember(
        slug="mia",
        name="Mia Trend",
        image="/static/crew/mia.png",
        ship_role="Lookout",
        operational_role="Trend Researcher",
        station="Crow's Nest",
        workflow_stage="Signal scan",
        mission_phase="1. Scout",
        summary="Scans the horizon for trends, signals, and timely opportunities.",
        personality="curious, alert, analytical",
        strengths=["trend sensing", "research", "signal detection"],
        watch_outs=["fresh signals still need strategic judgment"],
        inputs=["brief", "platforms"],
        outputs=["trend data", "formats", "timely context"],
        visual_signature="sky-blue accents, telescope details, wind-swept scout silhouette",
        accent_color="#4aa7d8",
        quote="The horizon always speaks first.",
    ),
    CrewMember(
        slug="zoe",
        name="Zoe Spark",
        image="/static/crew/zoe.png",
        ship_role="Cartographer of Ideas",
        operational_role="Idea Generator",
        station="Map Room",
        workflow_stage="Idea routes",
        mission_phase="2. Chart",
        summary="Turns research into creative routes worth pursuing.",
        personality="bright, imaginative, energetic",
        strengths=["ideation", "hooks", "angles"],
        watch_outs=["many routes still require one sharp choice"],
        inputs=["trend data", "brand context"],
        outputs=["idea set", "hooks", "content angles"],
        visual_signature="coral accents, map ribbons, expressive creative posture",
        accent_color="#e66f68",
        quote="One spark is enough to chart a new sea.",
    ),
    CrewMember(
        slug="bella",
        name="Bella Quill",
        image="/static/crew/bella.png",
        ship_role="Scribe",
        operational_role="Script Writer",
        station="Captain's Library",
        workflow_stage="Story draft",
        mission_phase="3. Write",
        summary="Shapes the chosen idea into words that sound like the brand.",
        personality="elegant, persuasive, empathetic",
        strengths=["voice", "structure", "copy"],
        watch_outs=["needs a strong idea to sing"],
        inputs=["selected idea", "brand voice"],
        outputs=["script", "article", "caption copy"],
        visual_signature="wine-red accents, quill details, refined editorial styling",
        accent_color="#a84a5f",
        quote="Every voyage needs a tale worth repeating.",
    ),
    CrewMember(
        slug="lila",
        name="Lila Lens",
        image="/static/crew/lila.png",
        ship_role="Visual Director",
        operational_role="Visual Creator",
        station="Studio Deck",
        workflow_stage="Visual build",
        mission_phase="4. Visualize",
        summary="Translates story into imagery, mood, and cinematic direction.",
        personality="stylish, visionary, polished",
        strengths=["composition", "visual language", "prompt direction"],
        watch_outs=["visual ambition must still serve the brief"],
        inputs=["script", "content type", "brand aesthetic"],
        outputs=["visual prompt", "image/video direction"],
        visual_signature="violet accents, camera-glass details, fashion-forward silhouette",
        accent_color="#8a6ed8",
        quote="If the eye believes it, the heart follows.",
    ),
    CrewMember(
        slug="nora",
        name="Nora Sharp",
        image="/static/crew/nora.png",
        ship_role="Inspector",
        operational_role="QA Editor",
        station="Inspection Bay",
        workflow_stage="Quality gate",
        mission_phase="5. Inspect",
        summary="Protects standards before anything leaves the ship.",
        personality="precise, honest, supportive",
        strengths=["review", "quality control", "risk spotting"],
        watch_outs=["perfection must not stall momentum"],
        inputs=["script", "visuals"],
        outputs=["QA verdict", "revision feedback"],
        visual_signature="silver accents, sharp tailoring, checklist and lens details",
        accent_color="#687386",
        quote="Better one hard truth on deck than one weak post at sea.",
    ),
    CrewMember(
        slug="roxy",
        name="Roxy Rise",
        image="/static/crew/roxy.png",
        ship_role="Trade Winds Strategist",
        operational_role="Growth Strategist",
        station="Signal Deck",
        workflow_stage="Distribution plan",
        mission_phase="6. Amplify",
        summary="Finds the best timing, framing, and route to reach the audience.",
        personality="upbeat, data-driven, tactical",
        strengths=["distribution", "hashtags", "timing"],
        watch_outs=["growth should amplify, not distort, the message"],
        inputs=["finished content", "platform context"],
        outputs=["caption", "hashtags", "posting timing"],
        visual_signature="sun-gold accents, signal flags, confident market tactician styling",
        accent_color="#d39a2f",
        quote="Even treasure needs the right tide.",
    ),
    CrewMember(
        slug="emma",
        name="Emma Heart",
        image="/static/crew/emma.png",
        ship_role="Community Keeper",
        operational_role="Community Specialist",
        station="Harbor Lounge",
        workflow_stage="Community prep",
        mission_phase="7. Welcome",
        summary="Prepares warm, useful responses for the people waiting on shore.",
        personality="warm, clear, attentive",
        strengths=["community care", "FAQ", "tone"],
        watch_outs=["kindness works best with clarity"],
        inputs=["final content", "brand context"],
        outputs=["FAQ", "response guidance"],
        visual_signature="rose accents, welcoming accessories, soft but capable presence",
        accent_color="#d56f9f",
        quote="A crew is remembered by how it welcomes people aboard.",
    ),
)


def get_crew_member(slug: str) -> CrewMember | None:
    return next((member for member in CREW if member.slug == slug), None)
