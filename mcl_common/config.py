from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):

    # Google Gemini & Cloud API Settings
    google_project_id: str = Field(alias="GOOGLE_PROJECT_ID")
    google_gemini_api_key: str = Field(alias="GOOGLE_GEMINI_API_KEY")
    google_gemini_model: str = Field(alias="GOOGLE_GEMINI_MODEL")
    google_embedding_model: str = Field(alias="GOOGLE_EMBEDDING_MODEL")
    google_embedding_dimensions: int = Field(alias="GOOGLE_EMBEDDING_DIMENSIONS")

    # Discord Bot Configuration
    discord_bot_token: str = Field(alias="DISCORD_BOT_TOKEN")
    discord_application_id: str = Field(alias="DISCORD_APPLICATION_ID")
    discord_public_key: str = Field(alias="DISCORD_PUBLIC_KEY")
    discord_ticket_channel_id: str = Field(alias="DISCORD_TICKET_CHANNEL_ID")
    discord_admin_channel_id: str = Field(alias="DISCORD_ADMIN_CHANNEL_ID")
    discord_open_channel_id: str = Field(alias="DISCORD_OPEN_CHANNEL_ID")

    # API, Security & Logging Configuration
    api_token: str = Field(alias="API_TOKEN")
    api_log_level: str = Field(default="DEBUG", alias="API_LOG_LEVEL")
    railway_data_directory: str = Field(default="data", alias="RAILWAY_DATA_DIRECTORY")
    allowed_ips: str = Field(default="", alias="ALLOWED_IPS")
    railway_environment_id: str = Field(alias="RAILWAY_ENVIRONMENT_ID")

    # MongoDB Configuration
    mcl_mongo_connection_string: str = Field(alias="MCL_MONGO_CONNECTION_STRING")
    mcl_mongo_database_help: str = Field(alias="MCL_MONGO_DATABASE_HELP")
    mcl_mongo_database_bot: str = Field(alias="MCL_MONGO_DATABASE_BOT")
    mcl_mongo_collection_tickets: str = Field(alias="MCL_MONGO_COLLECTION_TICKETS")
    mcl_mongo_collection_players: str = Field(alias="MCL_MONGO_COLLECTION_PLAYERS")
    mcl_mongo_collection_system_status: str = Field(alias="MCL_MONGO_COLLECTION_SYSTEM_STATUS")
    mcl_mongo_collection_server_status: str = Field(alias="MCL_MONGO_COLLECTION_SERVER_STATUS")

    # RAG Hyperparameters
    rag_hp_sourcescale_wiki: float = Field(default=1.0, alias="RAG_HP_SOURCESCALE_WIKI")
    rag_hp_sourcescale_faq: float = Field(default=1.0, alias="RAG_HP_SOURCESCALE_FAQ")
    rag_hp_recencyhalflife: float = Field(default=90.0, alias="RAG_HP_RECENCYHALFLIFE")
    rag_hp_seasonboost: float = Field(default=1.1, alias="RAG_HP_SEASONBOOST")
    rag_hp_semantic_cache_threshold: float = Field(alias="RAG_HP_SEMANTIC_CACHE_THRESHOLD")

    # Relaying & Network Routing Settings
    domain_minecraft_websocket: str = Field(alias="DOMAIN_MINECRAFT_WEBSOCKET")
    domain_discordbot_api: str = Field(alias="DOMAIN_DISCORDBOT_API")
    railway_api_domain: str = Field(alias="RAILWAY_API_DOMAIN")
    mcl_relay_queue_poll_interval: int = Field(alias="MCL_RELAY_QUEUE_POLL_INTERVAL")
    mcl_relay_queue_retry_interval: int = Field(alias="MCL_RELAY_QUEUE_RETRY_INTERVAL")

    # User Agent Identification Configurations
    user_agent_backend: str = Field(alias="USER_AGENT_BACKEND")
    user_agent_discordbot: str = Field(alias="USER_AGENT_DISCORDBOT")

    # AI Feature Toggle
    config_ai: bool = Field(default=True, alias="CONFIG_AI")

# Global settings instance
settings = Settings()
