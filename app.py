from flask import Flask, request, jsonify, Response
import subprocess
import os
from dotenv import load_dotenv
import tempfile
import glob
import re
import logging
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from a .env file for local development
load_dotenv()

app = Flask(__name__)

def get_transcript_with_yt_dlp(video_url, max_retries=3, retry_delay=5):
    """
    Uses yt-dlp to download the auto-generated transcript and return it as a plain text string.
    This version dynamically reads the YT_COOKIE environment variable to bypass bot detection.
    """
    for attempt in range(max_retries):
        # Use a temporary directory to ensure files are cleaned up automatically
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                logger.info(f"Created temporary directory: {tmpdir}")
                output_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
                cookies_file = os.path.join(tmpdir, 'cookies.txt')

                # --- DYNAMIC COOKIE FILE CREATION ---
                # ## <-- START OF CHANGES ##
                with open(cookies_file, 'w') as f:
                    # Write standard headers for the cookie file
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n\n")
                    
                    # Always add the CONSENT cookie as a fallback
                    f.write(".youtube.com\tTRUE\t/\tTRUE\t2147483647\tCONSENT\tYES+cb\n")

                    # Read the NID cookie from the environment variable
                    nid_cookie_string = os.environ.get('YT_COOKIE')
                    if nid_cookie_string and nid_cookie_string.startswith('NID='):
                        # The NID cookie is for the .google.com domain
                        # Format: domain<TAB>subdomains<TAB>path<TAB>secure<TAB>expires<TAB>name<TAB>value
                        cookie_line = ".google.com\tTRUE\t/\tTRUE\t2147483647\t" + nid_cookie_string.replace('=', '\t', 1) + "\n"
                        f.write(cookie_line)
                        logger.info("Successfully added NID cookie from YT_COOKIE environment variable.")
                    else:
                        logger.warning("YT_COOKIE environment variable not found or in wrong format. Proceeding without NID cookie.")
                # ## <-- END OF CHANGES ##

                command = [
                    'yt-dlp',
                    '--write-auto-sub',
                    '--sub-format', 'vtt',
                    '--skip-download',
                    '--cookies', cookies_file,  # Use our dynamically generated cookies file
                    '--no-check-certificates',
                    '--no-warnings',
                    '--extractor-args', 'youtube:player_client=android',
                    '-o', output_template,
                    video_url
                ]

                logger.info(f"Attempt {attempt + 1}/{max_retries}: Executing command: {' '.join(command)}")
                
                # ## <-- BUG FIX: Changed 'check=true' to 'check=True' ##
                result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
                
                logger.info(f"yt-dlp stdout: {result.stdout[:500]}...")
                # Only log stderr if it contains something (to avoid clutter)
                if result.stderr:
                    logger.warning(f"yt-dlp stderr: {result.stderr}")

                vtt_files = glob.glob(f"{tmpdir}/*.vtt")
                logger.info(f"Found {len(vtt_files)} vtt files: {vtt_files}")

                if not vtt_files:
                    raise FileNotFoundError("yt-dlp ran successfully but did not produce a .vtt file.")

                with open(vtt_files[0], 'r', encoding='utf-8') as f:
                    vtt_content = f.read()

                # VTT parsing logic
                lines = vtt_content.strip().split('\n')
                transcript_lines = []
                for line in lines:
                    if not line.strip() or '-->' in line or line.strip().isdigit() or line.startswith('WEBVTT') or line.startswith('Kind:'):
                        continue
                    clean_line = re.sub(r'<[^>]+>', '', line)
                    transcript_lines.append(clean_line.strip())

                if not transcript_lines:
                     raise ValueError("VTT file was found but contained no valid transcript lines.")

                logger.info(f"Successfully processed {len(transcript_lines)} transcript lines.")
                return " ".join(transcript_lines)

            except subprocess.CalledProcessError as e:
                # This block now specifically catches errors from yt-dlp
                logger.error(f"yt-dlp failed on attempt {attempt + 1} with a non-zero exit code.")
                logger.error(f"yt-dlp stderr: {e.stderr}") # The error message is in stderr
                if "HTTP Error 429" in e.stderr:
                    wait_time = retry_delay * (attempt + 1) + random.uniform(1, 3)
                    logger.warning(f"Rate limited. Waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                elif attempt >= max_retries - 1:
                    return None # Failed on last attempt
                else:
                    time.sleep(retry_delay)

            except Exception as e:
                logger.error(f"An unexpected error occurred on attempt {attempt + 1}: {str(e)}", exc_info=True)
                if attempt >= max_retries - 1:
                    return None # Failed on last attempt
                else:
                    time.sleep(retry_delay)

    return None # Return None if all retries fail


# --- Your Flask routes remain the same ---

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Please provide a YouTube URL in the request body'}), 400
    
    video_url = data['url']
    if not re.match(r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]+', video_url):
        return jsonify({'error': 'Invalid YouTube URL format'}), 400
    
    transcript = get_transcript_with_yt_dlp(video_url)
    
    if transcript:
        return Response(transcript, mimetype='text/plain')
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to get transcript. The video may not have captions, or the service may be temporarily blocked by YouTube.'
        }), 503 # 503 Service Unavailable is more appropriate here

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)