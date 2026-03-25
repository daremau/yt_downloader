import sys
import os
import subprocess
import tempfile
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QComboBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from pytubefix import YouTube
from pytubefix.contrib.playlist import Playlist


class FetchThread(QThread):
    info_signal = pyqtSignal(str, list, str)
    error_signal = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            if "playlist" in self.url.lower():
                playlist = Playlist(self.url)
                total = len(playlist.video_urls)
                self.info_signal.emit(
                    f"Playlist: {playlist.title}", [], f"Playlist ({total} videos)"
                )
            else:
                yt = YouTube(self.url)
                videos = yt.streams.filter(only_video=True)
                resolutions = sorted(
                    set(s.resolution for s in videos if s.resolution),
                    key=lambda x: int(x.replace("p", "")),
                    reverse=True,
                )
                self.info_signal.emit(
                    yt.title,
                    resolutions,
                    f"Duration: {yt.length // 60}:{yt.length % 60:02d}",
                )
        except Exception as e:
            self.error_signal.emit(str(e))


class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    current_video_signal = pyqtSignal(str, int, int)

    def __init__(self, url, output_path, quality):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.quality = quality

    def run(self):
        try:
            if "playlist" in self.url.lower():
                playlist = Playlist(self.url)
                videos = playlist.video_urls
                total = len(videos)
                for i, video_url in enumerate(videos, 1):
                    self.current_video_signal.emit(f"Video {i}/{total}", i, total)
                    self.download_video_with_audio(video_url, self.quality)
                self.finished_signal.emit(f"Playlist downloaded! ({total} videos)")
            else:
                self.download_video_with_audio(self.url, self.quality)
                self.finished_signal.emit("Download complete!")
        except Exception as e:
            self.error_signal.emit(f"Error: {e}")

    def download_video_with_audio(self, video_url, quality):
        yt = YouTube(video_url, on_progress_callback=self.on_progress)

        if quality == "Highest" or quality == "":
            video_stream = (
                yt.streams.filter(only_video=True).order_by("resolution").last()
            )
        else:
            video_stream = yt.streams.filter(
                only_video=True, resolution=quality
            ).first()
            if video_stream is None:
                video_stream = (
                    yt.streams.filter(only_video=True).order_by("resolution").last()
                )

        audio_stream = yt.streams.filter(only_audio=True).order_by("bitrate").last()

        with tempfile.TemporaryDirectory() as temp_dir:
            video_stream.download(output_path=temp_dir, filename="video")
            audio_stream.download(output_path=temp_dir, filename="audio")

            files = os.listdir(temp_dir)
            video_file = next((f for f in files if f.startswith("video")), None)
            audio_file = next((f for f in files if f.startswith("audio")), None)

            if video_file is None or audio_file is None:
                raise Exception("Failed to download video/audio")

            video_path = os.path.join(temp_dir, video_file)
            audio_path = os.path.join(temp_dir, audio_file)
            output_path = os.path.join(temp_dir, "output.mp4")

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_path,
                    "-i",
                    audio_path,
                    "-c",
                    "copy",
                    output_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if result.returncode != 0 or not os.path.exists(output_path):
                output_path = video_path

            filename = f"{yt.title}.mp4"
            final_path = os.path.join(self.output_path, filename)
            counter = 1
            while os.path.exists(final_path):
                filename = f"{yt.title}_{counter}.mp4"
                final_path = os.path.join(self.output_path, filename)
                counter += 1

            import shutil

            shutil.copy2(output_path, final_path)

    def on_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        pct = int(bytes_downloaded / total_size * 100)
        self.progress_signal.emit(pct)


class YoutubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.output_path = os.path.expanduser("~/Downloads")
        self.available_qualities = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Youtube Downloader")
        self.setGeometry(100, 100, 720, 520)

        layout = QVBoxLayout()

        self.title_label = QLabel("Insert a youtube link")
        layout.addWidget(self.title_label)

        url_layout = QHBoxLayout()
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Enter YouTube URL")
        self.link_input.textChanged.connect(self.on_url_changed)
        url_layout.addWidget(self.link_input)

        self.fetch_button = QPushButton("Fetch")
        self.fetch_button.clicked.connect(self.fetch_info)
        url_layout.addWidget(self.fetch_button)
        layout.addLayout(url_layout)

        self.video_info_label = QLabel("")
        layout.addWidget(self.video_info_label)

        path_layout = QHBoxLayout()
        self.path_label = QLabel(f"Save to: {self.output_path}")
        path_layout.addWidget(self.path_label)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.browse_button)
        layout.addLayout(path_layout)

        quality_layout = QHBoxLayout()
        quality_label = QLabel("Quality:")
        quality_layout.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Fetching..."])
        self.quality_combo.setEnabled(False)
        quality_layout.addWidget(self.quality_combo)
        layout.addLayout(quality_layout)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.video_label = QLabel("")
        layout.addWidget(self.video_label)

        self.percentage_label = QLabel("0%")
        layout.addWidget(self.percentage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setEnabled(False)
        layout.addWidget(self.download_button)

        self.setLayout(layout)

    def on_url_changed(self):
        self.video_info_label.setText("")
        self.quality_combo.clear()
        self.quality_combo.addItems(["Enter URL and click Fetch"])
        self.quality_combo.setEnabled(False)
        self.download_button.setEnabled(False)

    def fetch_info(self):
        url = self.link_input.text().strip()
        if not url:
            self.status_label.setText("Please enter a URL")
            return

        self.fetch_button.setEnabled(False)
        self.fetch_button.setText("Fetching...")

        self.thread = FetchThread(url)
        self.thread.info_signal.connect(self.on_fetch_success)
        self.thread.error_signal.connect(self.on_fetch_error)
        self.thread.start()

    def on_fetch_success(self, title, resolutions, extra_info):
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText("Fetch")

        if resolutions:
            self.video_info_label.setText(f"{title}\n{extra_info}")
            self.quality_combo.clear()
            self.quality_combo.addItems(["Highest"] + resolutions)
            self.quality_combo.setEnabled(True)
            self.download_button.setEnabled(True)
        else:
            self.video_info_label.setText(extra_info)
            self.quality_combo.clear()
            self.quality_combo.addItems(["Playlist detected - will download all"])
            self.quality_combo.setEnabled(False)
            self.download_button.setEnabled(True)

    def on_fetch_error(self, error):
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText("Fetch")
        self.status_label.setText(f"Error: {error}")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.output_path
        )
        if folder:
            self.output_path = folder
            self.path_label.setText(f"Save to: {self.output_path}")

    def start_download(self):
        url = self.link_input.text().strip()
        if not url:
            self.status_label.setText("Please enter a URL")
            return

        self.download_button.setEnabled(False)
        self.status_label.setText("Downloading...")
        self.video_label.setText("")
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")

        quality = self.quality_combo.currentText()
        self.thread = DownloadThread(url, self.output_path, quality)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished_signal.connect(self.download_finished)
        self.thread.error_signal.connect(self.download_error)
        self.thread.current_video_signal.connect(self.update_video_progress)
        self.thread.start()

    def update_video_progress(self, info, current, total):
        self.video_label.setText(info)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.percentage_label.setText(f"{value}%")

    def download_finished(self, message):
        self.status_label.setText(message)
        self.download_button.setEnabled(True)

    def download_error(self, message):
        self.status_label.setText(message)
        self.download_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YoutubeDownloader()
    window.show()
    sys.exit(app.exec())
