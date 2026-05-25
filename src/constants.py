from dotenv import load_dotenv
import os


load_dotenv()


class Constants:

    API_NAME = "Ougi Api"
    API_VERSION = "1.0.0"
    API_DESCR = "High-performance API for the Ougi ecosystem, managing the manhwa catalog, secure authentication, and community interactions."
    API_PREFIX = os.getenv("API_PREFIX")
    CLOUDFLARE_PREFIX = os.getenv("CLOUDFLARE_PREFIX")
    
    DEFAULT_AVATAR_SIZE = 120
    DEFAULT_BANNER_WIDTH = 1500
    DEFAULT_BANNER_HEIGHT = 500

    MAX_CHAPTER_COVER_SIZE = 5 * 1024 * 1024  # 5MB
    CHAPTER_COVER_MAX_WIDTH = 512

    IS_PRODUCTION = os.getenv("ENV", "dev").lower() == "prod"

    REFRESH_TOKEN_EXPIRE_DAYS = 3
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")


    MANHWA_COVER_TARGET_WIDTHS = {
        "big": 720,
        "medium": 320,
        "small": 160
    }

    MAX_FAILED_LOGIN_ATTEMPTS = 5

    RESTRICTED_NAMES = {        
        "ougi",
        "admin", 
        "adm", 
        "administrator",
        "sysadmin", 
        "owner", 
        "founder", 
        "ceo",
        "mod", 
        "moderator", 
        "moderador", 
        "dev", 
        "developer", 
        "creator",
        "staff", 
        "team", 
        "equipe", 
        "support", 
        "suporte", 
        "help", 
        "helpdesk",
        "system", 
        "sys", 
        "bot",
        "automod", 
        "server", 
        "webmaster",        
        "official", 
        "oficial", 
        "verified", 
        "verificado", 
        "security", 
        "seguranca"
    }