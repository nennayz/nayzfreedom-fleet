from __future__ import annotations
from pathlib import Path
import yaml
from models.content_job import PMProfile, BrandProfile, VisualIdentity

_PROJECT_ALIASES = {
    "slay_hack": "nayzfreedom_fleet",
}


class ProjectNotFoundError(Exception):
    pass


def resolve_project_slug(project_slug: str) -> str:
    return _PROJECT_ALIASES.get(project_slug, project_slug)


def project_slug_matches(left: str, right: str) -> bool:
    return resolve_project_slug(left) == resolve_project_slug(right)


def list_project_slugs(root: Path | None = None) -> list[str]:
    base = (root or Path(".")) / "projects"
    return sorted(p.parent.name for p in base.glob("*/pm_profile.yaml"))


def load_project(project_slug: str) -> PMProfile:
    resolved_slug = resolve_project_slug(project_slug)
    base = Path("projects") / resolved_slug
    if not base.exists():
        raise ProjectNotFoundError(f"Project '{project_slug}' not found in projects/")

    try:
        pm_data = yaml.safe_load((base / "pm_profile.yaml").read_text())
        brand_data = yaml.safe_load((base / "brand.yaml").read_text())
    except FileNotFoundError as e:
        raise ProjectNotFoundError(f"Missing required file in '{project_slug}': {e.filename}")
    except yaml.YAMLError as e:
        raise ProjectNotFoundError(f"Invalid YAML in '{project_slug}': {e}")

    extra: dict = {}
    if "allowed_content_types" in brand_data:
        extra["allowed_content_types"] = brand_data["allowed_content_types"]

    brand = BrandProfile(
        mission=brand_data["mission"],
        visual=VisualIdentity(**brand_data["visual"]),
        platforms=brand_data["platforms"],
        tone=brand_data["tone"],
        target_audience=brand_data["target_audience"],
        script_style=brand_data["script_style"],
        nora_max_retries=brand_data.get("nora_max_retries", 2),
        **extra,
    )
    return PMProfile(
        name=pm_data["name"],
        page_name=pm_data["page_name"],
        persona=pm_data["persona"].strip(),
        brand=brand,
    )


def load_platform_specs(project_slug: str) -> dict[str, str]:
    resolved_slug = resolve_project_slug(project_slug)
    base = Path("projects") / resolved_slug
    if not base.exists():
        raise ProjectNotFoundError(f"Project '{project_slug}' not found in projects/")
    specs_path = base / "platform_specs.yaml"
    if not specs_path.exists():
        return {}
    try:
        raw = yaml.safe_load(specs_path.read_text())
    except yaml.YAMLError as e:
        raise ProjectNotFoundError(f"Invalid YAML in platform_specs.yaml for '{project_slug}': {e}")
    return {platform: data["editorial"] for platform, data in raw.items()}
