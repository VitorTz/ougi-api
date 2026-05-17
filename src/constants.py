from dotenv import load_dotenv
import os


load_dotenv()


class Constants:

    API_NAME = os.getenv("API_NAME")
    API_VERSION = os.getenv("API_VERSION")
    API_DESCR =  os.getenv("API_DESCR")
    API_PREFIX = os.getenv("API_PREFIX")
    CLOUDFLARE_PREFIX = os.getenv("CLOUDFLARE_PREFIX")
    
    DEFAULT_AVATAR_SIZE = int(os.getenv("DEFAULT_AVATAR_SIZE", 120))
    DEFAULT_BANNER_WIDTH = int(os.getenv("DEFAULT_BANNER_WIDTH", 1500))
    DEFAULT_BANNER_HEIGHT = int(os.getenv("DEFAULT_BANNER_HEIGHT", 500))

    IS_PRODUCTION = os.getenv("ENV", "DEV").lower().upper() == "PROD"

    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")

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