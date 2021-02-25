from typing import cast
from pydantic import AnyHttpUrl, BaseSettings

class Settings(BaseSettings):
    PAPERO_SERVER: AnyHttpUrl = cast(AnyHttpUrl, "https://papero.io")

settings = Settings()

