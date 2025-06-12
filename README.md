# YouTube Transcript API

A Flask-based API service that uses yt-dlp to fetch transcripts from YouTube videos.

## Features

- Fetches auto-generated transcripts from YouTube videos
- Simple REST API interface
- Built with Flask and yt-dlp
- Ready for deployment on Render

## Prerequisites

- Python 3.8 or higher
- ffmpeg (installed automatically in production via build.sh)

## Local Development Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd yt-dlp-transcript-app
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install ffmpeg (if not already installed):
- On Ubuntu/Debian:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```
- On macOS:
```bash
brew install ffmpeg
```
- On Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

5. Run the application:
```bash
python app.py
```

The server will start at `http://localhost:5000`

## API Usage

### Get Transcript

**Endpoint:** `POST /api/transcript`

**Request Body:**
```json
{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**
```json
{
    "success": true,
    "transcript": "The full transcript text..."
}
```

**Error Response:**
```json
{
    "success": false,
    "error": "Error message here"
}
```

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
    "status": "healthy"
}
```

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your repository
3. Use the following settings:
   - Build Command: `bash build.sh`
   - Start Command: `gunicorn app:app`
   - Environment: Python 3
   - Plan: Free or higher

## Notes

- The service only works with videos that have auto-generated captions
- Some videos might not have available transcripts
- The API is rate-limited by YouTube's policies

## License

MIT # yt-dlp-transcript-app
