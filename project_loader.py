from __future__ import annotations
from pathlib import Path
import yaml
from models.content_job import PMProfile, BrandProfile, VisualIdentity


class ProjectNotFoundError(Exception):
    pass


def load_project(project_slug: str) -> PMProfile:
    base = Path("projects") / project_slug
    if not base.exists():
        raise ProjectNotFoundError(f"Project '{project_slug}' not found in projects/")

    try:
        pm_data = yaml.safe_load((base / "pm_profile.yaml").read_text())
        brand_data = yaml.safe_load((base / "brand.yaml").read_text())
    except FileNotFoundError as e:
        raise ProjectNotFoundError(f"Missing required file in '{project_slug}': {e.filename}")
    except yaml.YAMLError as e:
        raise ProjectNotFoundError(f"Invalid YAML in '{project_slug}': {e}")

    brand = BrandProfile(
        mission=brand_data["mission"],
        visual=VisualIdentity(**brand_data["visual"]),
        platforms=brand_data["platforms"],
        tone=brand_data["tone"],
        target_audience=brand_data["target_audience"],
        script_style=brand_data["script_style"],
        nora_max_retries=brand_data.get("nora_max_retries", 2),
    )
    return PMProfile(
        page_name=pm_data["page_name"],
        persona=pm_data["persona"].strip(),
        brand=brand,
    )
