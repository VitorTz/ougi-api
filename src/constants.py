from dotenv import load_dotenv
import os

load_dotenv()


class Constants:

    API_NAME = os.getenv("API_NAME")
    API_VERSION = os.getenv("API_VERSION")
    API_DESCR =  "API para o leitor de manwhas Ougi"

    IS_PRODUCTION = os.getenv("ENV", "DEV").lower().upper() == "PROD"

    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")

    MAX_BODY_SIZE = 20 * 1024 * 1024
    WINDOW = 30

    CLOUDFLARE_PREFIX = os.getenv("CLOUDFLARE_PREFIX")

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