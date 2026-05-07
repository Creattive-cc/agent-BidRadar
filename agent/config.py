from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    interval_hours: int = int(os.getenv("BIDRADAR_INTERVAL_HOURS", "6"))
    db_path: str = os.getenv("BIDRADAR_DB_PATH", "data/licitacoes.db")
    llm_provider: str = os.getenv("BIDRADAR_LLM_PROVIDER", "heuristic")
    vertex_project_id: str = os.getenv("BIDRADAR_VERTEX_PROJECT_ID", "")
    vertex_location: str = os.getenv("BIDRADAR_VERTEX_LOCATION", "us-central1")
    vertex_model: str = os.getenv("BIDRADAR_VERTEX_MODEL", "gemini-1.5-flash")
    google_application_credentials: str = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS", "service_account.json"
    )
    enable_comprasnet: bool = os.getenv("BIDRADAR_ENABLE_COMPRASNET", "true").lower() == "true"
    enable_bll: bool = os.getenv("BIDRADAR_ENABLE_BLL", "true").lower() == "true"
    # Codigos de modalidade PNCP (separados por virgula). Padrao: principais da Lei 14.133.
    pncp_modalidades: str = os.getenv(
        "BIDRADAR_PNCP_MODALIDADES",
        "1,2,3,4,5,6,7,8,9,10,11,12",
    )

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)

    @property
    def google_credentials_file(self) -> Path:
        return Path(self.google_application_credentials)


settings = Settings()
