from fastapi import Request, status, UploadFile
from fastapi.exceptions import HTTPException
from src.constants import Constants
from colorthief import ColorThief
from src.schemas.device_info import DeviceInfo
from src.schemas.manhwas import ManhwaCoverBytes
from datetime import datetime, timezone, date
from difflib import SequenceMatcher
from uuid6 import uuid7
from PIL import Image
import unicodedata
import traceback
import io
import uuid
import re


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def seconds_until(target: datetime) -> int:
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = (target - now).total_seconds()
    return int(diff) if diff > 0 else 0


def is_impostor_name(username: str) -> bool:
    # 1. Lowercase and remove all non-alphanumeric characters (including spaces, _, -)
    clean_name = re.sub(r'[^a-z0-9]', '', username.lower())
    
    # 2. Translate 'Leetspeak' (Hacker slang) back to standard characters
    leetspeak_map = {
        '0': 'o',
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '7': 't',
        '8': 'b',
        '@': 'a',
        '!': 'i'
    }
    
    translated_name = "".join(leetspeak_map.get(char, char) for char in clean_name)
    
    for restricted in Constants.RESTRICTED_NAMES:
        if restricted in translated_name:
            return True
    
    for restricted in Constants.RESTRICTED_NAMES:
        similarity = SequenceMatcher(None, translated_name, restricted).ratio()            
        if similarity > 0.75:
            return True
            
    return False


def format_stacktrace(exc: Exception) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def extract_client_ip(request: Request) -> str:
    """
    Extracts the real IP address of the user from the FastAPI Request object.
    It checks common proxy and CDN headers before falling back to the 
    direct client connection host.
    """    
    # 1. Cloudflare specific header (if you use Cloudflare)
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip

    # 2. Standard header used by most proxies and load balancers
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain a comma-separated list of IPs.
        # The first IP in the list is the original client IP.
        real_ip = x_forwarded_for.split(",")[0].strip()
        return real_ip

    # 3. Another common proxy header (often used by Nginx)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip

    # 4. Fallback: Direct connection IP (works on localhost or exposed servers)
    if request.client and request.client.host:
        return request.client.host

    # 5. Failsafe default if everything else is missing
    return "Unknown"


def extract_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "Unknown")


def get_device_info(request: Request) -> DeviceInfo:
    return DeviceInfo(
        device=request.headers.get("user-agent", "Unknown"),
        ip_address=extract_client_ip(request)
    )    


def is_of_legal_age(birthdate: date, legal_age: int = 18) -> bool:
    """
    Checks if a user is of legal age (default 18+) based on their birthdate.
    Essential for restricting access to adult manhwa content.
    """
    today = date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age >= legal_age


def validate_file_content(file: UploadFile) -> bool:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    

def validate_image_max_size(num_bytes: int) -> None:
    if num_bytes > Constants.MAX_CHAPTER_COVER_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
            detail=f"File size exceeds {Constants.MAX_CHAPTER_COVER_SIZE / 1024 / 1024:.0f}MB limit"
        )
    
    if num_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )


def extract_image_extension(header_bytes: bytes) -> str:
    """
    Validates if an uploaded file is a genuine image (JPEG, PNG, WEBP, GIF)
    by checking its 'magic numbers' (file signatures).
    Pass the first 12 bytes of the file (e.g., file.read(12)) to this function.
    """
    signatures = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
    }
    
    # WEBP signatures have 'RIFF' at the start and 'WEBP' at bytes 8-11
    if header_bytes.startswith(b'RIFF') and header_bytes[8:12] == b'WEBP':
        return "webp"
        
    for signature, ext in signatures.items():
        if header_bytes.startswith(signature):
            return ext
            
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    )

def validate_image_extension(header_bytes: bytes) -> None:
    extract_image_extension(header_bytes)


def generate_slug(title: str) -> str:
    normalized = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    normalized = normalized.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', normalized)
    return slug.strip('-')


def is_uuid(v: str):
    if isinstance(v, uuid.UUID): return True    
    
    try:
        uuid.UUID(v)
        return True
    except ValueError:
        return False
    

def generate_uuid_v7() -> str:
    return str(uuid7())


def extract_request_id(request: Request) -> str:
    # return getattr(request.state, "request_id", "unknown")
    return request.state.request_id


async def convert_to_webp(file_data: bytes, max_width: int = 512) -> tuple[bytes, tuple[int, int]]:
    try:
        img = Image.open(io.BytesIO(file_data))

        if img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = rgb_img

        if img.width > max_width:
            aspect_ratio = img.height / img.width
            new_height = int(max_width * aspect_ratio)
            
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        final_size = img.size
        
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=85, method=6)
        output.seek(0)        
        return output.getvalue(), final_size
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process image: {str(e)}"
        )


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 0:
        num_bytes = abs(num_bytes)
    
    unities = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    value = float(num_bytes)
    index = 0

    while value >= 1024 and index < len(unities) - 1:
        value /= 1024
        index += 1

    if value.is_integer():
        return f"{int(value)} {unities[index]}"
    else:
        return f"{value:.1f} {unities[index]}"
    

def get_dominant_hex_color(file: bytes, quality: int = 10) -> str:
    data = io.BytesIO(file)
    try:
        color_thief = ColorThief(data)
        dominant_rgb = color_thief.get_color(quality=quality)
        hex_color = "#{:02x}{:02x}{:02x}".format(*dominant_rgb).upper()
        return hex_color
    except Exception as e:
        print(f"Failed to extract color: {e}")
        return "#1A1A1A"
    

def create_manhwa_cover(image_bytes: bytes, quality: int = 85) -> ManhwaCoverBytes:
    try:
        original_image = Image.open(io.BytesIO(image_bytes))        
        if original_image.mode in ("RGBA", "LA", "P"):
            pass
        elif original_image.mode != "RGB":
            original_image = original_image.convert("RGB")
        
        original_width, original_height = original_image.size
        result = {}
        
        # Processa cada tamanho alvo
        for size_name, target_width in sorted(
            Constants.MANHWA_COVER_TARGET_WIDTHS.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            aspect_ratio = original_height / original_width
            target_height = int(target_width * aspect_ratio)
            resized_image = original_image.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS
            )
            
            # Converte para WebP
            webp_bytes = io.BytesIO()
            resized_image.save(
                webp_bytes,
                format="WebP",
                quality=quality,
                method=6
            )
            webp_bytes.seek(0)
            result[size_name] = webp_bytes
        return ManhwaCoverBytes(
            big=result['big'],
            medium=result['medium'],
            small=result['small']
        )
    except Image.UnidentifiedImageError:
        raise ValueError("Não foi possível identificar o formato da imagem")
    except Exception as e:
        raise ValueError(f"Erro ao processar a imagem: {str(e)}")
