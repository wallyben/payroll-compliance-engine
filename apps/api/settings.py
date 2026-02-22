from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24
    ruleset_version: str = "IE-2026.01"

    @model_validator(mode="after")
    def require_jwt_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and (
            not self.jwt_secret or self.jwt_secret.strip() == "" or self.jwt_secret == "change-me"
        ):
            raise ValueError("JWT_SECRET must be set when ENV=production")
        return self


settings = Settings()
