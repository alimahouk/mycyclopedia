import os
from enum import Enum, IntEnum


class AzureOpenAIDeployment:
    GPT_35 = "chat"
    GPT_35_16K = "gpt-35-turbo-16k"
    TEXT_EMBEDDING = "text-embedding-ada-002"


class ChatMessageSenderRole(str, Enum):
    ASSISTANT = "assistant"
    SYSTEM = "system"
    USER = "user"


class Configuration:
    DEBUG = False
    # --
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    AWS_EC2_PROD_DATABASE_01 = os.getenv("DB_HOST", "localhost")
    # Make sure this matches your local development server.
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000" if DEBUG else "https://mycyclopedia.co")
    CHAT_MESSAGE_MAX_LEN = 2048
    CHAT_PURGE_CHECK_INTERVAL = 60  # Seconds
    DATABASE_NAME = os.getenv("DB_NAME", "mycyclopedia")
    DATABASE_USER = os.getenv("DB_USER", "postgres")
    ENTRY_PURGE_CHECK_INTERVAL = 60  # Seconds
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_RETRY_MAX_ATTEMPTS = 5
    OPENAI_RETRY_DELAY = 3  # Seconds.
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    TOPIC_MAX_LEN = 256
    USER_ACCOUNT_MAX_COUNT = 5
    # --
    # DIRECTORY PATHS
    # --
    STATIC_DIR = os.path.join(APP_ROOT, "static")
    DOCS_DIR = os.path.join(STATIC_DIR, "docs")
    IMAGES_DIR = os.path.join(STATIC_DIR, "images")


class DatabaseTable:
    ANALYTICS_TOPIC_HISTORY = "analytics_topic_history_"
    CHAT = "chat_"
    CHAT_MESSAGE = "chat_message_"
    ENTRY = "entry_"
    ENTRY_COVER_IMAGE = "entry_cover_image_"
    ENTRY_FUN_FACT = "entry_fun_fact_"
    ENTRY_RELATED_TOPIC = "entry_related_topic_"
    ENTRY_SECTION = "entry_section_"
    ENTRY_STAT = "entry_stat_"
    USER = "user_"
    USER_SESSION = "user_session_"


class OpenAIModel:
    GPT_35 = "gpt-3.5-turbo"
    GPT_35_16K = "gpt-3.5-turbo-1106"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-1106-preview"


class ProtocolKey(str):
    CAPTION = "caption"
    CHAT = "chat"
    CHAT_ID = "chat_id"
    CONTENT_HTML = "content_html"
    CONTENT_MARKDOWN = "content_md"
    CONTEXT = "context"
    COVER_IMAGE = "cover_image"
    CREATION_DATE = "creation_date"
    CREATION_TIMESTAMP = "creation_timestamp"
    EMAIL_ADDRESS = "email_address"
    ENTRY_ID = "entry_id"
    ERROR = "error"
    ERROR_CODE = "error_code"
    ERROR_MESSAGE = "error_message"
    FUN_FACTS = "fun_facts"
    ID = "id"
    INDEX = "index"
    IP_ADDRESS = "ip_address"
    LAST_ACTIVITY = "last_activity"
    LOCATION = "location"
    MAC_ADDRESS = "mac_address"
    MESSAGE = "message"
    MESSAGE_ID = "message_id"
    MESSAGES = "messages"
    NAME = "name"
    NAME_HTML = "name_html"
    NAME_MARKDOWN = "name_md"
    OFFSET = "offset"
    PARENT_ID = "parent_id"
    PASSWORD = "password"
    PERMALINK = "permalink"
    PROFICIENCY = "proficiency"
    QUERY = "query"
    RELATED_TOPICS = "related_topics"
    RESET = "reset"
    SALT = "salt"
    SECTION_ID = "section_id"
    SECTIONS = "sections"
    SENDER = "sender"
    SENDER_ID = "sender_id"
    SENDER_ROLE = "sender_role"
    SESSION_ID = "session_id"
    SOURCE = "source"
    STATS = "stats"
    SUBSECTIONS = "subsections"
    SUMMARY = "summary"
    TITLE = "title"
    TOPIC = "topic"
    USER = "user"
    USER_ID = "user_id"
    USER_SESSION = "user_session"
    USER_SESSION_ID = "user_session_id"
    USER_SESSIONS = "user_sessions"
    USERS = "users"
    USER_ID = "user_id"
    URL = "url"
    VALUE_HTML = "value_html"
    VALUE_MARKDOWN = "value_md"


class ResponseStatus(IntEnum):
    # Generic
    OK = 0
    BAD_REQUEST = 1
    CREATED = 2
    FORBIDDEN = 3
    INTERNAL_SERVER_ERROR = 4
    NO_CONTENT = 5
    NOT_ALLOWED = 6
    NOT_FOUND = 7
    NOT_IMPLEMENTED = 8
    PAYLOAD_TOO_LARGE = 9
    TOO_MANY_REQUESTS = 10
    UNAUTHORIZED = 11
    # Specific
    ALREADY_EXISTS = 12
    CONTENT_MAX_LEN_EXCEEDED = 13
    CREDENTIALS_INVALID = 14
    EMAIL_FORMAT_INVALID = 15
    EMAIL_IN_USE = 16
    MESSAGE_CONTEXT_INVALID = 17
    PASSWORD_FORMAT_INVALID = 18
    SESSION_INVALID = 19
    USER_ACCOUNT_MAX_COUNT_REACHED = 20
    USER_NOT_FOUND = 21


class UserTopicProficiency(IntEnum):
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3

    def prompt_format(self) -> str:
        if self == UserTopicProficiency.BEGINNER:
            return "Beginner (struggles to grasp concepts pertaining to the topic so explain it as if speaking to a 5-year-old)"
        elif self == UserTopicProficiency.INTERMEDIATE:
            return "Intermediate (average level of understanding of concepts related to the topic)"
        elif self == UserTopicProficiency.ADVANCED:
            return "Advanced (strong grasp of concepts pertaining to the topic so explain it as if speaking to a professional)"
        else:
            return "Unknown Level"


openai_model_context_len = {
    OpenAIModel.GPT_35: 4_096,
    OpenAIModel.GPT_35_16K: 16_385,
    OpenAIModel.GPT_4: 8_192,
    OpenAIModel.GPT_4_TURBO: 128_000
}

openai_model_token_limits = {
    OpenAIModel.GPT_35: 4_096,
    OpenAIModel.GPT_35_16K: 4_096,
    OpenAIModel.GPT_4: 8_192,
    OpenAIModel.GPT_4_TURBO: 8_192
}

search_inspiration = [
    "A380",
    "Air Jordan",
    "Alan Turing",
    "Aleppo",
    "Alexander the Great",
    "Algorithm",
    "Android vs iOS",
    "Attack on Titan",
    "Bitcoin",
    "Burj Khalifa",
    "Calculus",
    "ChatGPT",
    "Economies of Scale",
    "Generative AI",
    "History of Sandwiches",
    "Hundred Years' War",
    "IBM Model M",
    "Lev Landau",
    "London",
    "The C Programming Language",
    "The End of Greatness",
    "The Founding of Rome",
    "The Global Financial Crisis",
    "The Original Macintosh Team",
    "The Tube",
    "The Western Approaches",
    "Tokyo",
    "Mac vs Windows",
    "Powerlifting vs Weightlifting",
    "Satoshi Nakamoto",
    "Saturn V",
    "Solo Traveler Lid",
    "SR-71",
    "Steve Jobs",
    "Wikipedia",
    "World War I",
    "World Wide Web",
    "Wright Flyer"
]
