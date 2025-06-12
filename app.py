from flask import Flask, request, jsonify, Response
import subprocess
import os
from dotenv import load_dotenv
import tempfile
import glob
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

def get_transcript_with_yt_dlp(video_url):
    """
    Uses yt-dlp to download the auto-generated transcript and return it as a plain text string.
    """
    try:
        # Use a temporary directory to store the subtitle file
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"Created temporary directory: {tmpdir}")
            output_template = f"{tmpdir}/%(id)s.%(ext)s"
            command = [
                'yt-dlp',
                '--write-auto-sub',    # Write the auto-generated subtitle file
                '--sub-format', 'vtt', # Specify the format (vtt is common)
                '--skip-download',     # Don't download the video
                '-o', output_template,
                video_url
            ]
            logger.info(f"Executing command: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)
            logger.info(f"yt-dlp stdout: {result.stdout[:500]}...")
            logger.info(f"yt-dlp stderr: {result.stderr}")
            
            # Find the .vtt file
            vtt_files = glob.glob(f"{tmpdir}/*.vtt")
            logger.info(f"Found {len(vtt_files)} vtt files: {vtt_files}")
            if not vtt_files:
                logger.error("No .vtt file found after yt-dlp run.")
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
                logger.error("No transcript lines found after filtering")
                return None
            return " ".join(transcript_lines)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
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