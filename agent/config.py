import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

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
    enable_comprasnet: bool = (
        os.getenv("BIDRADAR_ENABLE_COMPRASNET", "true").lower() == "true"
    )
    enable_bll: bool = os.getenv("BIDRADAR_ENABLE_BLL", "true").lower() == "true"
    enable_conlicitacao: bool = (
        os.getenv("BIDRADAR_ENABLE_CONLICITACAO", "true").lower() == "true"
    )
    # Codigos de modalidade PNCP (separados por virgula). Padrao: principais da Lei 14.133.
    pncp_modalidades: str = os.getenv(
        "BIDRADAR_PNCP_MODALIDADES",
        "1,2,3,4,5,6,7,8,9,10,11,12",
    )
    # GCP: projeto que hospeda BigQuery, Pub/Sub e Firestore (pode diferir do projeto Vertex).
    gcp_project_id: str = os.getenv(
        "BIDRADAR_GCP_PROJECT_ID", "creattive-licitacoes-dev"
    )
    bigquery_dataset: str = os.getenv("BIDRADAR_BQ_DATASET", "licitacoes")
    bigquery_table: str = os.getenv("BIDRADAR_BQ_TABLE", "editais")
    pubsub_topic: str = os.getenv("BIDRADAR_PUBSUB_TOPIC", "coleta-editais")
    jwt_secret_key: str = os.getenv(
        "BIDRADAR_JWT_SECRET", "change-me-in-production-very-long-random-string"
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("BIDRADAR_JWT_EXPIRE_MINUTES", "480"))
    admin_email: str = os.getenv("BIDRADAR_ADMIN_EMAIL", "admin@bidradar.local")
    admin_password: str = os.getenv("BIDRADAR_ADMIN_PASSWORD", "admin123")

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)

    @property
    def google_credentials_file(self) -> Path:
        return Path(self.google_application_credentials)


settings = Settings()
