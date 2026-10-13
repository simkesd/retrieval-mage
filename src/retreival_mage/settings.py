import os
from dataclasses import dataclass
from dotenv import load_dotenv

class ConfigError(Exception):
    pass

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    generation_model: str

    @classmethod
    def from_env(cls) -> 'Settings':
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ConfigError("GROQ_API_KEY is not set!")
        return cls(
            groq_api_key=api_key,
            generation_model=os.environ["GENERATION_MODEL"],
        )