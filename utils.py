import os
import tempfile
import hashlib
from urllib.parse import urlparse, unquote
from pathlib import Path
import mimetypes
from config import SUPPORTED_IMAGE_FORMATS, SUPPORTED_VIDEO_FORMATS, logger

def get_file_extension_from_url(url):
    """Extract file extension from URL"""
    parsed_url = urlparse(url)
    path = unquote(parsed_url.path)
    return Path(path).suffix.lower()

def get_file_extension_from_content_type(content_type):
    """Get file extension from content-type header"""
    if not content_type:
        return None
    
    extension = mimetypes.guess_extension(content_type.split(';')[0])
    return extension.lower() if extension else None

def is_supported_media(file_path_or_url):
    """Check if file is supported media format"""
    if file_path_or_url.startswith('http'):
        ext = get_file_extension_from_url(file_path_or_url)
    else:
        ext = Path(file_path_or_url).suffix.lower()
    
    return ext in SUPPORTED_IMAGE_FORMATS or ext in SUPPORTED_VIDEO_FORMATS

def is_image(file_path_or_url):
    """Check if file is an image"""
    if file_path_or_url.startswith('http'):
        ext = get_file_extension_from_url(file_path_or_url)
    else:
        ext = Path(file_path_or_url).suffix.lower()
    
    return ext in SUPPORTED_IMAGE_FORMATS

def is_video(file_path_or_url):
    """Check if file is a video"""
    if file_path_or_url.startswith('http'):
        ext = get_file_extension_from_url(file_path_or_url)
    else:
        ext = Path(file_path_or_url).suffix.lower()
    
    return ext in SUPPORTED_VIDEO_FORMATS

def create_temp_file(content, extension=None):
    """Create a temporary file with content"""
    suffix = extension if extension and extension.startswith('.') else f'.{extension}' if extension else ''
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return temp_file.name

def cleanup_temp_file(file_path):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

def get_file_hash(file_path):
    """Get MD5 hash of file"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return None

def validate_url(url):
    """Validate if URL is properly formatted"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def get_filename_from_url(url):
    """Extract filename from URL"""
    parsed_url = urlparse(url)
    path = unquote(parsed_url.path)
    filename = Path(path).name
    
    # If no filename found, generate one
    if not filename or '.' not in filename:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"media_{url_hash}"
    
    return filename
