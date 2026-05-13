from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv


class MissingAPIKeyError(Exception):
    pass


@dataclass
class Config:
    anthropic_api_key: str
    brave_search_api_key: str
    openai_api_key: str
    google_cloud_project: str = ""
    google_application_credentials: str = ""
    meta_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_user_id: str = ""
    tiktok_access_token: str = ""
    youtube_api_key: str = ""

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            raise MissingAPIKeyError("ANTHROPIC_API_KEY is required")
        return cls(
            anthropic_api_key=anthropic_key,
            brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            google_application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
            meta_access_token=os.getenv("META_ACCESS_TOKEN", ""),
            meta_page_id=os.getenv("META_PAGE_ID", ""),
            meta_ig_user_id=os.getenv("META_IG_USER_ID", ""),
            tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        )
