from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "P.Y.T.A"
    port: int = 8000
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    debug: bool = False
    db_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    db_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    db_password: str = Field(default="example", validation_alias="POSTGRES_PASSWORD")
    db_name: str = Field(default="postgres", validation_alias="POSTGRES_DB")

    logs_amount_to_keep: int = 1

    testing: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
