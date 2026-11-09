"""全局配置。优先级: 环境变量 > .env 文件 > 默认值。

现阶段 llm_provider=mock (内置规则推理, 无需 API Key 即可跑通端到端)。
后续接真实 DeepSeek: 将 .env 中 LLM_PROVIDER 改为 deepseek 并填 DEEPSEEK_API_KEY。
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录
BASE_DIR = Path(__file__).resolve().parent.parent

# Docker/PaaS 环境下可用 STORAGE_DIR 环境变量指定持久化路径
_STORAGE_BASE = Path(os.environ.get("STORAGE_DIR", str(BASE_DIR / "storage")))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "HARA / PRD 差异分析智能体"
    cors_origins: str = "*"  # 逗号分隔; * 表示全部放行 (开发用)

    # ---- 大模型 (需求③) ----
    llm_provider: str = "mock"  # mock | deepseek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---- 路径 ----
    base_dir: Path = BASE_DIR
    storage_dir: Path = _STORAGE_BASE
    uploads_dir: Path = _STORAGE_BASE / "uploads"
    reports_dir: Path = _STORAGE_BASE / "reports"
    templates_dir: Path = BASE_DIR / "templates"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.storage_dir / 'app.db').as_posix()}"

    @property
    def template_path(self) -> Path:
        return self.templates_dir / "report_template.docx"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # 确保运行期目录存在
    for d in (s.storage_dir, s.uploads_dir, s.reports_dir, s.templates_dir):
        d.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
