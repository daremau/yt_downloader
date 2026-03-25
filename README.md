# Video Downloader

A desktop application for downloading videos and playlists in various qualities.

## Features

- Download single videos or entire playlists
- Quality selection (360p to 4K)
- Per-video quality selection for playlists
- Custom download directory
- Progress tracking

## Requirements

- Python 3.9+
- ffmpeg (system installation required)

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install python3-tk ffmpeg
```

**Fedora:**
```bash
sudo dnf install python3-tk ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install PyQt6 pytubefix
```

## Usage

1. Activate the virtual environment:
```bash
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
```

2. Run the application:
```bash
python main.py
```

3. Enter a URL and click "Fetch" to load video/playlist info
4. Select quality for each video (or use "Apply to all" for playlists)
5. Choose download location with "Browse"
6. Click "Download"

## Notes

- Videos above 720p require ffmpeg to merge video and audio streams
- The app fetches available qualities for each video individually in playlists
- If selected quality is unavailable, highest available quality is used
