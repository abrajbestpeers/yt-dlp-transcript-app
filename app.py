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
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

def get_transcript_with_yt_dlp(video_url, max_retries=3, retry_delay=5):
    """
    Uses yt-dlp to download the auto-generated transcript and return it as a plain text string.
    Includes retry logic for rate limiting.
    """
    for attempt in range(max_retries):
        try:
            # Use a temporary directory to store the subtitle file
            with tempfile.TemporaryDirectory() as tmpdir:
                logger.info(f"Created temporary directory: {tmpdir}")
                output_template = f"{tmpdir}/%(id)s.%(ext)s"
                
                # Create a cookies file with minimal required cookies
                cookies_file = os.path.join(tmpdir, 'cookies.txt')
                with open(cookies_file, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                    f.write("# This is a generated file! Do not edit.\n\n")
                    f.write(".youtube.com\tTRUE\t/\tTRUE\t2147483647\tCONSENT\tYES+cb\n")
                
                # Base command with cookies support
                command = [
                    'yt-dlp',
                    '--write-auto-sub',    # Write the auto-generated subtitle file
                    '--sub-format', 'vtt', # Specify the format (vtt is common)
                    '--skip-download',     # Don't download the video
                    '--cookies', cookies_file,  # Use our cookies file
                    '--no-check-certificates',  # Sometimes helps with connection issues
                    '--no-warnings',       # Reduce noise in logs
                    '--extractor-args', 'youtube:player_client=android',  # Use mobile client
                    '-o', output_template,
                    video_url
                ]
                
                logger.info(f"Attempt {attempt + 1}/{max_retries}: Executing command: {' '.join(command)}")
                result = subprocess.run(command, capture_output=True, text=True)
                
                # Check for rate limiting
                if "HTTP Error 429" in result.stderr:
                    wait_time = retry_delay * (attempt + 1) + random.uniform(1, 3)
                    logger.warning(f"Rate limited. Waiting {wait_time:.1f} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                
                logger.info(f"yt-dlp stdout: {result.stdout[:500]}...")
                logger.info(f"yt-dlp stderr: {result.stderr}")
                
                # Find the .vtt file
                vtt_files = glob.glob(f"{tmpdir}/*.vtt")
                logger.info(f"Found {len(vtt_files)} vtt files: {vtt_files}")
                if not vtt_files:
                    if attempt < max_retries - 1:
                        logger.warning(f"No .vtt file found on attempt {attempt + 1}. Will retry...")
                        continue
                    logger.error("No .vtt file found after all attempts.")
                    return None
                
                vtt_file = vtt_files[0]
                logger.info(f"Processing vtt file: {vtt_file}")
                
                with open(vtt_file, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()
                lines = vtt_content.strip().split('\n')
                transcript_lines = []
                for line in lines:
                    if not line.strip():
                        continue
                    if '-->' in line:
                        continue
                    if line.strip().isdigit():
                        continue
                    if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                        continue
                    # Remove timestamp and tag patterns like <00:00:01.439><c>
                    clean_line = re.sub(r'<[^>]+>', '', line)
                    transcript_lines.append(clean_line.strip())
                
                logger.info(f"Processed {len(transcript_lines)} transcript lines")
                if not transcript_lines:
                    if attempt < max_retries - 1:
                        logger.warning(f"No transcript lines found on attempt {attempt + 1}. Will retry...")
                        continue
                    logger.error("No transcript lines found after all attempts.")
                    return None
                return " ".join(transcript_lines)
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {str(e)}", exc_info=True)
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue
            return None
    
    return None

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    """
    API endpoint to get transcript from a YouTube video URL.
    Expects a JSON payload with a 'url' field containing the YouTube video URL.
    """
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({'error': 'Please provide a YouTube URL in the request body'}), 400
    
    video_url = data['url']
    
    # Validate URL (basic check)
    if not video_url.startswith(('https://www.youtube.com/', 'https://youtu.be/')):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    transcript = get_transcript_with_yt_dlp(video_url)
    
    if transcript:
        return Response(transcript, mimetype='text/plain')
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to get transcript. The video might not have auto-generated captions.'
        }), 404

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 