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
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from pytubefix import YouTube
from pytubefix.contrib.playlist import Playlist


class FetchThread(QThread):
    info_signal = pyqtSignal(str, list, str, list)
    loading_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            if "playlist" in self.url.lower():
                playlist = Playlist(self.url)
                video_urls = playlist.video_urls
                total = len(video_urls)
                video_info_list = []

                for i, video_url in enumerate(video_urls):
                    yt = YouTube(video_url)
                    videos = yt.streams.filter(only_video=True)
                    resolutions = sorted(
                        set(s.resolution for s in videos if s.resolution),
                        key=lambda x: int(x.replace("p", "")),
                        reverse=True,
                    )
                    video_info_list.append(
                        {
                            "title": yt.title,
                            "resolutions": resolutions,
                            "url": video_url,
                        }
                    )
                    self.loading_signal.emit(f"Loading video {i + 1}/{total}...")

                self.info_signal.emit(
                    playlist.title,
                    [f"{total} videos"],
                    f"Playlist ({total} videos)",
                    video_info_list,
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
                    [],
                )
        except Exception as e:
            self.error_signal.emit(str(e))


class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    current_video_signal = pyqtSignal(str, int, int)
    video_warning_signal = pyqtSignal(int, str)

    def __init__(self, videos_data, output_path):
        super().__init__()
        self.videos_data = videos_data
        self.output_path = output_path

    def run(self):
        try:
            total = len(self.videos_data)
            for i, video_data in enumerate(self.videos_data, 1):
                video_url = video_data["url"]
                quality = video_data["quality"]

                self.current_video_signal.emit(f"Video {i}/{total}", i, total)

                has_quality = quality in video_data["available_qualities"]
                if not has_quality and quality != "Highest":
                    self.video_warning_signal.emit(
                        i, f"Quality {quality} not available - using highest"
                    )

                self.download_video_with_audio(
                    video_url, quality, video_data.get("available_qualities", [])
                )

            self.finished_signal.emit(f"Downloaded {total} videos!")
        except Exception as e:
            self.error_signal.emit(f"Error: {e}")

    def download_video_with_audio(self, video_url, quality, available_qualities):
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
        self.video_items = []
        self.is_playlist = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Youtube Downloader")
        self.setGeometry(100, 100, 720, 600)

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

        self.quality_container = QVBoxLayout()
        self.mass_quality_layout = QHBoxLayout()
        mass_label = QLabel("Apply to all:")
        self.mass_quality_layout.addWidget(mass_label)
        self.mass_quality_combo = QComboBox()
        self.mass_quality_combo.addItems(["Highest", "1080p", "720p", "480p", "360p"])
        self.mass_quality_combo.setCurrentText("Highest")
        self.mass_quality_combo.currentTextChanged.connect(self.apply_mass_quality)
        self.mass_quality_combo.setEnabled(False)
        self.mass_quality_layout.addWidget(self.mass_quality_combo)
        self.quality_container.addLayout(self.mass_quality_layout)
        layout.addLayout(self.quality_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(200)
        self.video_list_widget = QWidget()
        self.video_list_layout = QVBoxLayout()
        self.video_list_widget.setLayout(self.video_list_layout)
        self.scroll_area.setWidget(self.video_list_widget)
        layout.addWidget(self.scroll_area)

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

    def clear_video_list(self):
        while self.video_list_layout.count():
            item = self.video_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.video_items = []

    def on_url_changed(self):
        self.video_info_label.setText("")
        self.clear_video_list()
        self.download_button.setEnabled(False)
        self.mass_quality_combo.setEnabled(False)

    def fetch_info(self):
        url = self.link_input.text().strip()
        if not url:
            self.status_label.setText("Please enter a URL")
            return

        self.fetch_button.setEnabled(False)
        self.fetch_button.setText("Fetching...")
        self.clear_video_list()

        self.thread = FetchThread(url)
        self.thread.info_signal.connect(self.on_fetch_success)
        self.thread.loading_signal.connect(self.on_loading_progress)
        self.thread.error_signal.connect(self.on_fetch_error)
        self.thread.start()

    def on_loading_progress(self, message):
        self.video_info_label.setText(message)

    def on_fetch_success(self, title, resolutions, extra_info, video_info_list):
        self.fetch_button.setEnabled(True)
        self.fetch_button.setText("Fetch")

        if video_info_list:
            self.is_playlist = True
            self.video_info_label.setText(f"{title}\n{extra_info}")
            self.mass_quality_combo.setEnabled(True)

            for i, video in enumerate(video_info_list):
                self.add_video_item(
                    i + 1, video["title"], video["resolutions"], video["url"]
                )

            self.download_button.setEnabled(True)
        else:
            self.is_playlist = False
            self.video_info_label.setText(f"{title}\n{extra_info}")
            self.add_video_item(1, title, resolutions, self.link_input.text().strip())
            self.download_button.setEnabled(True)

    def add_video_item(self, num, title, resolutions, url):
        item_widget = QWidget()
        item_layout = QHBoxLayout()

        num_label = QLabel(f"{num}.")
        num_label.setFixedWidth(30)
        item_layout.addWidget(num_label)

        title_label = QLabel(title)
        title_label.setFixedWidth(300)
        title_label.setWordWrap(True)
        item_layout.addWidget(title_label)

        quality_combo = QComboBox()
        quality_combo.addItems(["Highest"] + resolutions)
        quality_combo.setCurrentText("Highest")
        quality_combo.setFixedWidth(100)
        item_layout.addWidget(quality_combo)

        warning_label = QLabel("")
        warning_label.setFixedWidth(150)
        warning_label.setStyleSheet("color: orange;")
        item_layout.addWidget(warning_label)

        item_widget.setLayout(item_layout)
        self.video_list_layout.addWidget(item_widget)

        self.video_items.append(
            {
                "widget": item_widget,
                "combo": quality_combo,
                "warning": warning_label,
                "url": url,
                "resolutions": resolutions,
            }
        )

    def apply_mass_quality(self):
        quality = self.mass_quality_combo.currentText()
        for item in self.video_items:
            item["combo"].setCurrentText(quality)
            self.update_warning(item, quality)

    def update_warning(self, item, selected_quality):
        if selected_quality == "Highest" or selected_quality in item["resolutions"]:
            item["warning"].setText("")
        else:
            item["warning"].setText(
                f"⚠ {selected_quality} not available - using highest"
            )

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
        if not self.video_items:
            self.status_label.setText("No videos to download")
            return

        self.download_button.setEnabled(False)
        self.status_label.setText("Downloading...")
        self.progress_bar.setValue(0)
        self.percentage_label.setText("0%")

        videos_data = []
        for item in self.video_items:
            videos_data.append(
                {
                    "url": item["url"],
                    "quality": item["combo"].currentText(),
                    "available_qualities": item["resolutions"],
                }
            )

        self.thread = DownloadThread(videos_data, self.output_path)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished_signal.connect(self.download_finished)
        self.thread.error_signal.connect(self.download_error)
        self.thread.current_video_signal.connect(self.update_video_progress)
        self.thread.video_warning_signal.connect(self.handle_video_warning)
        self.thread.start()

    def handle_video_warning(self, video_num, message):
        if video_num <= len(self.video_items):
            self.video_items[video_num - 1]["warning"].setText(f"⚠ {message}")

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
