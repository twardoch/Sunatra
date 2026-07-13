import os
import re
import time
import threading
import json
import requests
import appdirs
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TCON, COMM, TDRC, TYER, USLT, TXXX
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import platform
import subprocess


# --- UUID cache ---
# Persists {filepath: {"mtime": float, "uuid": str|None}} so repeated library
# scans skip ID3 reads for files that haven't changed. Stale entries (file
# missing) are pruned each save. None uuids are cached too — files without a
# SUNO_UUID don't need to be re-parsed every run.

_UUID_CACHE_LOCK = threading.Lock()
_UUID_CACHE_PATH = os.path.join(
    appdirs.user_data_dir("SunoSync", "InternetThot"),
    "uuid_cache.json",
)


def _load_uuid_cache():
    if not os.path.exists(_UUID_CACHE_PATH):
        return {}
    try:
        with open(_UUID_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _save_uuid_cache(cache):
    try:
        os.makedirs(os.path.dirname(_UUID_CACHE_PATH), exist_ok=True)
        with open(_UUID_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except OSError:
        pass


def _path_in_dir(path_norm, directory_norm):
    """True if *path_norm* is *directory_norm* itself or lives beneath it.
    Both args must already be normcase+normpath'd. Guards against sibling
    directories whose names share a prefix (e.g. Music vs MusicBackup)."""
    return path_norm == directory_norm or path_norm.startswith(directory_norm + os.sep)


def _scan_with_uuid_cache(directory, exts):
    """
    Walk *directory* and return a dict {filepath: uuid_or_none} for every file
    matching one of the *exts*. Uses _UUID_CACHE_PATH on disk; only re-reads ID3
    when a file's mtime has changed.
    """
    if not os.path.exists(directory):
        return {}

    with _UUID_CACHE_LOCK:
        cache = _load_uuid_cache()
        result = {}
        seen_paths = set()
        dirty = False

        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if not fname.lower().endswith(exts):
                    continue
                filepath = os.path.join(root, fname)
                seen_paths.add(filepath)
                try:
                    mtime = os.path.getmtime(filepath)
                except OSError:
                    continue

                cached = cache.get(filepath)
                if cached and cached.get("mtime") == mtime:
                    result[filepath] = cached.get("uuid")
                    continue

                uuid = get_uuid_from_file(filepath)
                cache[filepath] = {"mtime": mtime, "uuid": uuid}
                result[filepath] = uuid
                dirty = True

        # Prune entries for files that no longer exist (or moved out of scope).
        # Only prune entries that *would* have been included in this scan — i.e.
        # under the same directory tree — so partial scans don't wipe siblings.
        # Use normcase + a trailing separator so scanning "C:\Music" doesn't match
        # a sibling like "C:\MusicBackup", and casing differences don't defeat it.
        directory_norm = os.path.normcase(os.path.normpath(directory))
        for stale in [
            p for p in cache
            if _path_in_dir(os.path.normcase(os.path.normpath(p)), directory_norm)
            and p not in seen_paths
        ]:
            del cache[stale]
            dirty = True

        if dirty:
            _save_uuid_cache(cache)

        return result


def open_file(path):
    """Open file or folder with default system application."""
    try:
        if not path or not os.path.exists(path):
            print(f"Cannot open path: {path}")
            return
            
        path = os.path.normpath(path)
        
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.call(('open', path))
        else:  # Linux
            subprocess.call(('xdg-open', path))
    except Exception as e:
        print(f"Error opening file {path}: {e}")


def get_uuid_from_file(filepath):
    """
    Extract SUNO_UUID from audio file metadata.
    Returns None if UUID not found or file cannot be read.
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".wav":
            audio = WAVE(filepath)
        elif ext == ".mp3":
            audio = MP3(filepath, ID3=ID3)
        else:
            return None
        
        if not hasattr(audio, 'tags') or audio.tags is None:
            return None
        
        # Look for SUNO_UUID in TXXX tags
        for key in audio.tags.keys():
            if key.startswith("TXXX:"):
                tag = audio.tags[key]
                if hasattr(tag, 'desc') and tag.desc == "SUNO_UUID":
                    return str(tag.text[0]) if tag.text else None
        
        return None
    except Exception:
        return None


def build_uuid_cache(directory):
    """
    Scan directory recursively and build a set of all UUIDs found in audio files.
    Returns a set of UUID strings. Backed by an mtime-keyed disk cache so
    repeated scans skip ID3 reads for unchanged files.
    """
    return {uuid for uuid in _scan_with_uuid_cache(directory, (".mp3", ".wav")).values() if uuid}


def extract_genre_from_prompt(prompt_text):
    """
    Extract genre information from Suno prompt text.
    Takes the first 3-4 meaningful words/keywords.
    
    Args:
        prompt_text: The prompt or description text from Suno
        
    Returns:
        str: Extracted genre (max 20 chars) or None
    """
    if not prompt_text or not isinstance(prompt_text, str):
        return None
    
    # Clean up the text
    text = prompt_text.strip()
    if not text:
        return None
    
    # Common patterns: "Dark Techno, fast tempo" or "Indie Rock with emotional vocals"
    # Take first part before common separators
    separators = [',', 'with', 'featuring', '|', '-', 'and']
    for sep in separators:
        if sep in text.lower():
            text = text.split(sep)[0].strip()
            break
    
    # Take first 3-4 words (up to 20 chars)
    words = text.split()[:4]
    genre = ' '.join(words)
    
    # Truncate to 20 chars if needed
    if len(genre) > 20:
        genre = genre[:17] + "..."
    
    return genre if genre else None


def extract_bpm_from_prompt(prompt_text):
    """
    Extract BPM (tempo) from Suno prompt text using regex.
    
    Args:
        prompt_text: The prompt or description text from Suno
        
    Returns:
        str: BPM value as string or None
    """
    if not prompt_text or not isinstance(prompt_text, str):
        return None
    
    # Regex pattern to find "120 bpm" or "120bpm" (case-insensitive)
    pattern = r'(\d+)\s*bpm'
    match = re.search(pattern, prompt_text, re.IGNORECASE)
    
    if match:
        bpm_value = match.group(1)
        # Validate BPM is in reasonable range (40-300)
        try:
            bpm_int = int(bpm_value)
            if 40 <= bpm_int <= 300:
                return str(bpm_int)
        except ValueError:
            pass
    
    return None


def is_uuid_like(text):
    """Check if text looks like a UUID (long alphanumeric with dashes)."""
    if not text or len(text) < 30:
        return False
    # UUID pattern: 8-4-4-4-12 hex characters
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(uuid_pattern, text.lower()))


def clean_title(title_text):
    """
    Clean up messy titles that look like raw lists or prompt artifacts.
    e.g. "['control: bouncy, crisp...']" -> "Untitled Track" (or extracted genre)
    """
    if not title_text:
        return "Untitled Track"
    
    # 1. Check for list-like strings
    # If it starts with [' or [ and contains internal structure signs like control: or verse]
    if (title_text.startswith("['") or title_text.startswith("[")) and \
       ("control:" in title_text.lower() or "verse]" in title_text.lower() or "chorus]" in title_text.lower()):
        # It's a prompt artifact
        # Try to extract genre/vibe from it before finding 'Untitled'
        # Remove list chars
        clean = title_text.replace("['", "").replace("']", "").replace("[", "").replace("]", "")
        genre = extract_genre_from_prompt(clean)
        if genre:
            return f"Untitled ({genre})"
        return "Untitled Track"
        
    # 2. Cleanup general dirt (quotes, brackets at ends)
    # e.g. "['My Song']" -> "My Song"
    if title_text.startswith("['") and title_text.endswith("']"):
        title_text = title_text[2:-2]
    elif title_text.startswith('[') and title_text.endswith(']'):
        title_text = title_text[1:-1]
        
    return title_text

def get_display_title(title, prompt_text=None):
    """
    Get a user-friendly display title.
    If title is a UUID, use prompt text or 'Untitled Track'.
    Also cleans up messy prompt artifacts.
    
    Args:
        title: The raw title from metadata
        prompt_text: Optional prompt text to extract title from
        
    Returns:
        str: User-friendly title
    """
    if not title:
        return "Untitled Track"
    
    # Clean the title first
    title = clean_title(title)
        
    # Check if title looks like a UUID
    if is_uuid_like(title):
        if prompt_text and prompt_text.strip():
            # Extract first 4-5 words from prompt
            words = prompt_text.strip().split()[:5]
            if words:
                display_title = ' '.join(words)
                # Capitalize first letter
                display_title = display_title[0].upper() + display_title[1:] if len(display_title) > 1 else display_title.upper()
                # Truncate if too long
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."
                return display_title
        
        return "Untitled Track"
    
    return title


def read_song_metadata(filepath):
    """
    Reads metadata from MP3/WAV file for library display.
    
    Returns: {
        'title': str,
        'artist': str,
        'duration': int (seconds),
        'date': str,
        'filepath': str,
        'filesize': int (bytes)
    }
    """
    result = {
        'title': os.path.basename(filepath),
        'artist': 'Unknown Artist',
        'genre': '--',
        'bpm': '--',
        'duration': 0,
        'date': '',
        'filepath': filepath,
        'filesize': 0,
        'lyrics': ''
    }
    
    try:
        # Get file stats
        stat = os.stat(filepath)
        result['filesize'] = stat.st_size
        result['date'] = time.strftime('%Y-%m-%d', time.localtime(stat.st_mtime))
        
        # Read audio metadata
        ext = os.path.splitext(filepath)[1].lower()
        audio = None
        
        if ext == '.wav':
            audio = WAVE(filepath)
        elif ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
        
        if audio:
            # Duration
            if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                result['duration'] = int(audio.info.length)
            
            # Tags
            if hasattr(audio, 'tags') and audio.tags:
                # Title
                if 'TIT2' in audio.tags:
                    result['title'] = str(audio.tags['TIT2'].text[0])
                
                # Artist  
                if 'TPE1' in audio.tags:
                    result['artist'] = str(audio.tags['TPE1'].text[0])

                # Genre
                if 'TCON' in audio.tags:
                    result['genre'] = str(audio.tags['TCON'].text[0])
                
                # BPM
                if 'TBPM' in audio.tags:
                    result['bpm'] = str(audio.tags['TBPM'].text[0])
                
                # Lyrics (USLT) - check all USLT frames and use the first non-empty one
                for key in audio.tags.keys():
                    if key.startswith('USLT'):
                        lyrics_text = str(audio.tags[key].text)
                        if lyrics_text and lyrics_text.strip():
                            result['lyrics'] = lyrics_text
                            break
                
                # Fallback to filename if no title tag
                if result['title'] == os.path.basename(filepath) and 'TIT2' not in audio.tags:
                    # Try to parse filename (remove extension and clean up)
                    name = os.path.splitext(os.path.basename(filepath))[0]
                    result['title'] = name.replace('_', ' ')
                
                # Smart parsing: Extract Genre/BPM from prompt text if missing
                prompt_text = None
                
                # Look for prompt in TXXX tags (custom text frames)
                for key in audio.tags.keys():
                    if key.startswith('TXXX:'):
                        tag = audio.tags[key]
                        if hasattr(tag, 'desc'):
                            # Check for common prompt field names
                            if tag.desc.lower() in ['prompt', 'gpt_description_prompt', 'description']:
                                prompt_text = str(tag.text[0]) if tag.text else None
                                break
                
                # Fallback: Check COMM (comment) tags
                if not prompt_text:
                    for key in audio.tags.keys():
                        if key.startswith('COMM:'):
                            comment_text = str(audio.tags[key].text)
                            if comment_text and len(comment_text) > 20:  # Likely a prompt if it's long enough
                                prompt_text = comment_text
                                break
                
                # Apply smart parsing if we found a prompt
                if prompt_text:
                    # Clean up escaped newlines in prompt
                    prompt_text = prompt_text.replace('\\n', '\n')
                    
                    # Store prompt for later use
                    result['prompt'] = prompt_text
                    
                    # Extract Genre if missing
                    if result['genre'] == '--':
                        extracted_genre = extract_genre_from_prompt(prompt_text)
                        if extracted_genre:
                            result['genre'] = extracted_genre
                    
                    # Extract BPM if missing
                    if result['bpm'] == '--':
                        extracted_bpm = extract_bpm_from_prompt(prompt_text)
                        if extracted_bpm:
                            result['bpm'] = extracted_bpm
        
        # If no lyrics in metadata, check for .txt file
        if not result['lyrics'] or result['lyrics'].strip() == '':
            txt_path = os.path.splitext(filepath)[0] + ".txt"
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        result['lyrics'] = f.read()
                except Exception:
                    pass  # Silently fail if .txt file can't be read
        
        # Check for Artwork (Design Doc Item 3)
        image_path = None
        # 1. Check same name .jpg
        jpg_path = os.path.splitext(filepath)[0] + ".jpg"
        if os.path.exists(jpg_path):
            image_path = jpg_path
        else:
            # 2. Check cover.jpg in folder
            cover_path = os.path.join(os.path.dirname(filepath), "cover.jpg")
            if os.path.exists(cover_path):
                image_path = cover_path
        
        result['image_path'] = image_path
        
        # Get UUID
        result['id'] = get_uuid_from_file(filepath)
        
        # Fix UUID titles - apply display title logic
        result['title'] = get_display_title(result['title'], result.get('prompt'))
    
    except Exception as e:
        # On any error, fall back to the filename-only stub but surface the
        # cause so silent metadata corruption is diagnosable.
        print(f"Metadata read failed for {filepath}: {e}")

    return result


def save_lyrics_to_file(filepath, lyrics):
    """Update lyrics in the audio file."""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        audio = None
        
        if ext == '.wav':
            audio = WAVE(filepath)
            if audio.tags is None:
                audio.add_tags()
        elif ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
        
        if audio:
            # Remove existing USLT frames
            to_delete = [key for key in audio.tags.keys() if key.startswith('USLT')]
            for key in to_delete:
                del audio.tags[key]
            
            # Add new USLT frame
            # encoding=3 is UTF-8, desc='' is standard for main lyrics
            audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
            
            if ext == '.mp3':
                # v2.3 is most compatible with Windows/Players
                audio.save(v2_version=3)
            else:
                audio.save()
                
            return True, "Saved successfully"
            
    except Exception as e:
        print(f"Error saving lyrics to {filepath}: {e}")
        return False, str(e)
    return False, "Unknown error or invalid file type"


def save_metadata_to_file(filepath, metadata_dict):
    """
    Save metadata to audio file.
    
    Args:
        filepath: Path to audio file
        metadata_dict: Dict with keys like 'title', 'artist', 'genre', 'bpm', 'prompt', 'lyrics'
    
    Returns:
        bool: True if successful
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        audio = None
        
        if ext == '.mp3':
            from mutagen.id3 import ID3, TIT2, TPE1, TCON, TBPM, USLT, TXXX
            try:
                audio = ID3(filepath)
            except Exception:
                audio = ID3()
        elif ext == '.wav':
            from mutagen.wave import WAVE
            audio = WAVE(filepath)
        else:
            return False
        
        if not audio:
            return False
        
        # Update tags
        if ext == '.mp3':
            # Title
            if 'title' in metadata_dict and metadata_dict['title']:
                audio['TIT2'] = TIT2(encoding=3, text=metadata_dict['title'])
            
            # Artist
            if 'artist' in metadata_dict and metadata_dict['artist']:
                audio['TPE1'] = TPE1(encoding=3, text=metadata_dict['artist'])
            
            # Genre
            if 'genre' in metadata_dict and metadata_dict['genre']:
                audio['TCON'] = TCON(encoding=3, text=metadata_dict['genre'])
            
            # BPM
            if 'bpm' in metadata_dict and metadata_dict['bpm']:
                audio['TBPM'] = TBPM(encoding=3, text=str(metadata_dict['bpm']))
            
            # Prompt (store in TXXX)
            if 'prompt' in metadata_dict and metadata_dict['prompt']:
                audio['TXXX:prompt'] = TXXX(encoding=3, desc='prompt', text=metadata_dict['prompt'])
            
            # Lyrics
            if 'lyrics' in metadata_dict and metadata_dict['lyrics']:
                audio['USLT'] = USLT(encoding=3, lang='eng', desc='', text=metadata_dict['lyrics'])
            
            audio.save(filepath)
        
        elif ext == '.wav':
            # WAV uses INFO tags
            if 'title' in metadata_dict and metadata_dict['title']:
                audio['INAM'] = metadata_dict['title']
            
            if 'artist' in metadata_dict and metadata_dict['artist']:
                audio['IART'] = metadata_dict['artist']
            
            if 'genre' in metadata_dict and metadata_dict['genre']:
                audio['IGNR'] = metadata_dict['genre']
            
            audio.save()
        
        return True
        
    except Exception as e:
        print(f"Error saving metadata to {filepath}: {e}")
        return False


FILENAME_BAD_CHARS = r'[<>:"/\\|?*\x00-\x1F]'


def hex_to_rgb(color):
    color = color.lstrip("#")
    if len(color) in (6, 8):
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_colors(color_a, color_b, ratio):
    a = hex_to_rgb(color_a)
    b = hex_to_rgb(color_b)
    ratio = max(0.0, min(1.0, ratio))
    return rgb_to_hex(tuple(int(max(0, min(255, a[i] + (b[i] - a[i]) * ratio))) for i in range(3)))


def lighten_color(color, amount=0.1):
    rgb = hex_to_rgb(color)
    return rgb_to_hex(tuple(max(0, min(255, int(c + (255 - c) * amount))) for c in rgb))


def sanitize_filename(name, maxlen=200):
    safe = re.sub(FILENAME_BAD_CHARS, "_", name)
    safe = safe.strip(" .")
    return safe[:maxlen] if len(safe) > maxlen else safe


def reserve_unique_path(filename, max_attempts=200):
    """Atomically reserve *filename* (or a `Title vN.ext` variant) by creating
    a 0-byte file with O_CREAT|O_EXCL. Returns the reserved path. Race-safe
    across threads and processes — unlike a plain existence check, which has a
    TOCTOU window between the existence check and the actual write that lets
    two concurrent downloaders pick the same path and clobber each other.

    Caller is responsible for opening the returned path for writing (the file
    will be empty/truncatable). Raises RuntimeError if no unique name found
    within max_attempts.
    """
    name, extn = os.path.splitext(filename)
    candidate = filename
    attempt = 1
    while attempt <= max_attempts:
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return candidate
        except FileExistsError:
            attempt += 1
            candidate = f"{name} v{attempt}{extn}"
    raise RuntimeError(f"Could not reserve a unique filename starting from {filename!r} after {max_attempts} attempts")


def get_downloaded_uuids(directory):
    """
    Return the set of SUNO_UUIDs found in .mp3 files under *directory*.
    Backed by an mtime-keyed disk cache so repeated scans skip ID3 reads for
    unchanged files.
    """
    return {uuid for uuid in _scan_with_uuid_cache(directory, (".mp3",)).values() if uuid}


class RateLimiter:
    """Simple token-style rate limiter that enforces a minimum delay between calls."""

    def __init__(self, min_interval=0.0):
        self.min_interval = max(0.0, float(min_interval))
        self._lock = threading.Lock()
        self._next_allowed = time.monotonic()

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next_allowed = now + self.min_interval


def embed_metadata(
    audio_path,
    image_url=None,
    title=None,
    artist=None,
    album=None,
    genre=None,
    year=None,
    comment=None,
    lyrics=None,
    uuid=None,
    token=None,
    timeout=15,
    metadata_options=None,
):
    """
    Embed metadata into MP3 or WAV files.
    
    metadata_options: dict with keys 'title', 'artist', 'genre', 'year', 
                     'comment', 'lyrics', 'album_art', 'uuid' (all bool)
    """
    if metadata_options is None:
        # Default: include all metadata
        metadata_options = {
            'title': True, 'artist': True, 'genre': True, 'year': True,
            'comment': True, 'lyrics': True, 'album_art': True, 'uuid': True
        }
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        # Determine file type
        ext = os.path.splitext(audio_path)[1].lower()
        is_wav = ext == ".wav"
        
        # Load audio file
        if is_wav:
            audio = WAVE(audio_path)
        else:
            audio = MP3(audio_path, ID3=ID3)
        
        # Add ID3 tags if they don't exist
        if not hasattr(audio, 'tags') or audio.tags is None:
            audio.add_tags()
        
        # Get image if needed
        image_bytes = None
        mime = "image/jpeg"
        if metadata_options.get('album_art', True) and image_url:
            r = requests.get(image_url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                image_bytes = r.content
                mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]

        # Embed metadata fields based on options
        if metadata_options.get('title', True) and title:
            audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        if metadata_options.get('artist', True) and artist:
            audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        if metadata_options.get('genre', True) and genre:
            audio.tags["TCON"] = TCON(encoding=3, text=genre)
        if metadata_options.get('year', True) and year:
            audio.tags["TDRC"] = TDRC(encoding=3, text=str(year))
            audio.tags["TYER"] = TYER(encoding=3, text=str(year))
        if metadata_options.get('comment', True) and comment:
            audio.tags["COMM"] = COMM(encoding=3, lang="eng", desc="Description", text=comment)
        
        # 1. Extract Lyrics
        # Suno stores lyrics in 'prompt'. We check 'lyrics' and 'text' just in case.
        # Note: 'lyrics' variable already contains the extracted text from suno_downloader.py
        lyrics_text = lyrics
        

        if lyrics_text and metadata_options.get('lyrics', True):
            try:
                # Remove existing USLT frames first
                to_delete = [key for key in audio.tags.keys() if key.startswith('USLT')]
                for key in to_delete:
                    del audio.tags[key]
                
                # Add lyrics to both MP3 and WAV files
                # For WAV files, ensure tags exist
                if isinstance(audio, WAVE):
                    if audio.tags is None:
                        audio.add_tags()
                
                # Add USLT frame with lyrics
                audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics_text))
                print(f"Lyrics successfully embedded for {os.path.basename(audio_path)}")
                
            except Exception as e:
                print(f"Failed to embed lyrics: {e}")
                import traceback
                traceback.print_exc()

        if metadata_options.get('uuid', True) and uuid:
            audio.tags.add(TXXX(encoding=3, desc="SUNO_UUID", text=uuid))

        if image_bytes:
            for key in list(audio.tags.keys()):
                if key.startswith("APIC"):
                    del audio.tags[key]
            audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_bytes))

        # Save: MP3 uses v2_version, WAV doesn't support it
        if is_wav:
            audio.save()
        else:
            audio.save(v2_version=3)
    except Exception as e:
        print(f"Metadata error: {e}")


# --- GUI UTILS ---
def truncate_path(path, max_length=40):
    """Truncate path with middle ellipsis."""
    if len(path) <= max_length:
        return path
    folder_name = os.path.basename(path)
    parent = os.path.dirname(path)
    if len(folder_name) > max_length - 10:
        return f"...{folder_name[-max_length+3:]}"
    return f"{parent[:15]}...{os.sep}{folder_name}"


def safe_messagebox(func, *args, suppress_sound=False, **kwargs):
    """
    Wrapper for messagebox functions that can suppress Windows notification sounds.
    
    Args:
        func: messagebox function (showinfo, showwarning, showerror, askyesno, etc.)
        *args: Arguments to pass to the messagebox function
        suppress_sound: If True, suppress Windows notification sound
        **kwargs: Keyword arguments to pass to the messagebox function
    
    Returns:
        The result of the messagebox function
    """
    if not suppress_sound:
        return func(*args, **kwargs)

    # Mute the Tk bell for the duration of the dialog, restoring it afterwards.
    # If anything about the bell fiddling fails, just show the dialog normally.
    import tkinter as tk
    root = tk._default_root
    if root is None:
        return func(*args, **kwargs)
    try:
        original_volume = root.tk.call('set', 'bell_volume')
        root.tk.call('set', 'bell_volume', '0')
    except Exception:
        return func(*args, **kwargs)
    try:
        return func(*args, **kwargs)
    finally:
        try:
            root.tk.call('set', 'bell_volume', original_volume)
        except Exception:
            pass



def copy_files_to_clipboard(file_list):
    """
    Copy list of files to Windows Clipboard (CF_HDROP).
    Allows pasting files into Explorer, DAW, etc.
    """
    try:
        import win32clipboard
        import win32con
        
        # pywin32 handles DROPFILES struct creation automatically if passed list of strings to CF_HDROP
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, file_list)
        win32clipboard.CloseClipboard()
        return True
        
    except ImportError:
        print("pywin32 not found. Please install it: pip install pywin32")
        return False
    except Exception as e:
        print(f"Clipboard error: {e}")
        return False
