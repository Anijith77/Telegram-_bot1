import requests
from bs4 import BeautifulSoup
import yt_dlp
import tempfile
import os
from urllib.parse import urljoin, urlparse
import re
from PIL import Image
from config import (
    MAX_PHOTO_SIZE, MAX_VIDEO_SIZE, MAX_DOCUMENT_SIZE, 
    DOWNLOAD_TIMEOUT, MAX_RETRIES, USER_AGENT, logger
)
from utils import (
    get_file_extension_from_url, get_file_extension_from_content_type,
    is_supported_media, is_image, is_video, create_temp_file,
    validate_url, get_filename_from_url
)

class MediaExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        
        # yt-dlp configuration
        self.ydl_opts = {
            'format': 'best[filesize<50M]',
            'no_warnings': True,
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_subtitles': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    def extract_media_from_url(self, url):
        """Main method to extract media from URL"""
        if not validate_url(url):
            raise ValueError("Invalid URL format")
        
        logger.info(f"Extracting media from: {url}")
        
        # Try different extraction methods
        try:
            # First, try direct media URL
            if self._is_direct_media_url(url):
                return self._download_direct_media(url)
            
            # Try yt-dlp for video platforms
            media_files = self._extract_with_ytdlp(url)
            if media_files:
                return media_files
            
            # Try web scraping for embedded media
            media_files = self._scrape_media_from_page(url)
            if media_files:
                return media_files
            
            raise ValueError("No supported media found on this URL")
            
        except Exception as e:
            logger.error(f"Error extracting media from {url}: {e}")
            raise
    
    def _is_direct_media_url(self, url):
        """Check if URL points directly to media file"""
        ext = get_file_extension_from_url(url)
        return is_supported_media(url) or self._check_content_type(url)
    
    def _check_content_type(self, url):
        """Check content-type header to determine if it's media"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()
            
            return (content_type.startswith('image/') or 
                   content_type.startswith('video/') or
                   'image' in content_type or 'video' in content_type)
        except Exception as e:
            logger.debug(f"Error checking content type for {url}: {e}")
            return False
    
    def _download_direct_media(self, url):
        """Download media directly from URL"""
        try:
            response = self.session.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
            response.raise_for_status()
            
            # Check file size
            content_length = response.headers.get('content-length')
            if content_length:
                size = int(content_length)
                if size > MAX_DOCUMENT_SIZE:
                    raise ValueError(f"File too large: {size} bytes (max: {MAX_DOCUMENT_SIZE})")
            
            # Determine file extension
            content_type = response.headers.get('content-type')
            ext = get_file_extension_from_content_type(content_type) or get_file_extension_from_url(url)
            
            # Download content
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > MAX_DOCUMENT_SIZE:
                    raise ValueError("File too large during download")
            
            # Validate content is actually media, not HTML
            content_type = response.headers.get('content-type', '').lower()
            if content_type.startswith('text/html') or b'<html' in content[:1000].lower():
                raise ValueError("Downloaded content is HTML, not media")
            
            # Create temporary file with proper extension
            filename = get_filename_from_url(url)
            
            # Determine proper extension based on content-type
            if content_type.startswith('image/'):
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'  # default for images
            
            temp_path = create_temp_file(content, ext)
            
            # Determine media type more accurately
            is_image_type = (content_type.startswith('image/') or 
                           is_image(temp_path) or 
                           is_image(url) or
                           any(filename.lower().endswith(img_ext) for img_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']))
            
            is_video_type = (content_type.startswith('video/') or 
                           is_video(temp_path) or 
                           is_video(url) or
                           any(filename.lower().endswith(vid_ext) for vid_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v']))
            
            media_type = 'image' if is_image_type else 'video' if is_video_type else 'document'
            
            media_info = {
                'file_path': temp_path,
                'filename': filename,
                'size': len(content),
                'type': media_type,
                'url': url,
                'content_type': content_type
            }
            
            logger.info(f"Downloaded direct media: {filename} ({len(content)} bytes)")
            return [media_info]
            
        except Exception as e:
            logger.error(f"Error downloading direct media from {url}: {e}")
            raise
    
    def _extract_with_ytdlp(self, url):
        """Extract media using yt-dlp"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Get info without downloading
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Handle playlist
                if 'entries' in info:
                    # Take only the first video from playlist
                    entries = list(info['entries'])
                    if not entries:
                        return None
                    info = entries[0]
                
                # Check if it's a supported format
                formats = info.get('formats', [])
                if not formats:
                    return None
                
                # Find best format within size limits
                best_format = None
                for fmt in formats:
                    filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                    if filesize and filesize <= MAX_VIDEO_SIZE:
                        if not best_format or (fmt.get('quality', 0) > best_format.get('quality', 0)):
                            best_format = fmt
                
                if not best_format:
                    # Try without size check
                    best_format = formats[0] if formats else None
                
                if best_format:
                    # Download the media
                    temp_dir = tempfile.mkdtemp()
                    download_opts = self.ydl_opts.copy()
                    download_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')
                    
                    with yt_dlp.YoutubeDL(download_opts) as ydl_download:
                        ydl_download.download([url])
                    
                    # Find downloaded file
                    downloaded_files = []
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        if os.path.isfile(file_path) and is_supported_media(file_path):
                            file_size = os.path.getsize(file_path)
                            
                            media_info = {
                                'file_path': file_path,
                                'filename': file,
                                'size': file_size,
                                'type': 'video' if is_video(file_path) else 'image',
                                'url': url,
                                'title': info.get('title', 'Unknown')
                            }
                            downloaded_files.append(media_info)
                    
                    if downloaded_files:
                        logger.info(f"Extracted {len(downloaded_files)} media files using yt-dlp")
                        return downloaded_files
                
                return None
                
        except Exception as e:
            logger.debug(f"yt-dlp extraction failed for {url}: {e}")
            return None
    
    def _scrape_media_from_page(self, url):
        """Scrape media URLs from web page"""
        try:
            response = self.session.get(url, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            media_urls = set()
            
            # Special handling for Google Images
            if 'google.com' in url and 'tbm=isch' in url:
                # Extract image URLs from Google Images search results
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # Look for image URLs in JavaScript data
                        import re
                        img_matches = re.findall(r'"(https?://[^"]*\.(?:jpg|jpeg|png|gif|webp)(?:\?[^"]*)?)"', script.string)
                        for match in img_matches:
                            if 'googleusercontent.com' in match or 'wikimedia.org' in match:
                                media_urls.add(match)
                                if len(media_urls) >= 3:  # Limit Google Images results
                                    break
                        if len(media_urls) >= 3:
                            break
            
            # Find images in img tags
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    img_url = urljoin(url, src)
                    # Skip tiny images and tracking pixels
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w < 100 or h < 100:  # Skip small images
                                continue
                        except ValueError:
                            pass
                    
                    if is_supported_media(img_url) and 'data:image' not in img_url:
                        media_urls.add(img_url)
            
            # Check data-src attributes (lazy loading)
            for img in soup.find_all('img', attrs={'data-src': True}):
                data_src = img.get('data-src')
                if data_src:
                    img_url = urljoin(url, data_src)
                    if is_supported_media(img_url):
                        media_urls.add(img_url)
            
            # Find videos
            for video in soup.find_all('video', src=True):
                src = video.get('src')
                if src:
                    video_url = urljoin(url, src)
                    if is_supported_media(video_url):
                        media_urls.add(video_url)
            
            # Find video sources
            for source in soup.find_all('source', src=True):
                src = source.get('src')
                if src:
                    source_url = urljoin(url, src)
                    if is_supported_media(source_url):
                        media_urls.add(source_url)
            
            # Find links to media files
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href:
                    link_url = urljoin(url, href)
                    if is_supported_media(link_url):
                        media_urls.add(link_url)
            
            # Try to find Open Graph images
            og_image = soup.find('meta', property='og:image')
            if og_image:
                content = og_image.get('content')
                if content:
                    img_url = urljoin(url, content)
                    if is_supported_media(img_url):
                        media_urls.add(img_url)
            
            # Download found media
            downloaded_media = []
            for media_url in list(media_urls)[:5]:  # Limit to 5 media files
                try:
                    media_files = self._download_direct_media(media_url)
                    downloaded_media.extend(media_files)
                except Exception as e:
                    logger.debug(f"Failed to download media from {media_url}: {e}")
                    continue
            
            if downloaded_media:
                logger.info(f"Scraped {len(downloaded_media)} media files from page")
                return downloaded_media
            
            return None
            
        except Exception as e:
            logger.error(f"Error scraping media from {url}: {e}")
            return None
