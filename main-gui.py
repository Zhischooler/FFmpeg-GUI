import sys
import os
import subprocess
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QComboBox, 
                               QLineEdit, QFileDialog, QPlainTextEdit, QListWidget, 
                               QStackedWidget, QFormLayout)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont

QSS = """
QMainWindow, QWidget {
    background-color: #111111;
    color: #EAEAEA;
    font-family: 'JetBrains Mono', 'Microsoft YaHei', 'PingFang SC', monospace;
    font-size: 13px;
}
QLabel.title {
    font-family: 'Playfair Display', 'Georgia', 'Songti SC', serif;
    font-size: 36px;
    color: #FFFFFF;
    letter-spacing: 2px;
    font-weight: bold;
    line-height: 1.2;
}
QLabel { color: #888888; }
QPushButton {
    background-color: #1A1A1A;
    color: #FFFFFF;
    border: 1px solid #333333;
    padding: 12px 24px;
    font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
    font-size: 13px;
    letter-spacing: 1px;
}
QPushButton:hover {
    background-color: #FFFFFF;
    color: #111111;
    border-color: #FFFFFF;
}
QPushButton:pressed { background-color: #CCCCCC; }
QPushButton:disabled { color: #444444; border-color: #222222; }
QComboBox, QLineEdit {
    background-color: #1A1A1A;
    color: #EAEAEA;
    border: 1px solid #333333;
    padding: 10px;
    min-height: 20px;
    font-family: 'JetBrains Mono', monospace;
}
QComboBox:focus, QLineEdit:focus { border: 1px solid #FFFFFF; outline: none; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid #EAEAEA; }
QListWidget {
    background-color: #111111;
    border: 1px solid #222222;
    color: #EAEAEA;
    padding: 10px;
}
QListWidget::item { padding: 8px 0; border-bottom: 1px solid #1A1A1A; }
QListWidget::item:selected { background-color: #1A1A1A; color: #FFFFFF; border-left: 2px solid #FFFFFF; }
QPlainTextEdit {
    background-color: #0A0A0A;
    color: #00FF9C;
    border: 1px solid #222222;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    padding: 16px;
}
QGroupBox {
    border: 1px solid #222222;
    margin-top: 24px;
    padding-top: 16px;
    font-family: 'Playfair Display', 'Songti SC', serif;
    font-size: 16px;
    color: #FFFFFF;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
"""

class FFmpegWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, ffmpeg_path, files, output_dir, task_type, params):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.files = files
        self.output_dir = output_dir
        self.task_type = task_type
        self.params = params

    def run(self):
        for file in self.files:
            filename = os.path.basename(file)
            name, _ = os.path.splitext(filename)
            self.log_signal.emit(f"▶ 处理中: {filename}")
            
            out_ext = self.params.get('out_ext', '.mp4')
            out_name = f"{name}_out{out_ext}"
            out_path = os.path.join(self.output_dir, out_name)

            cmd = [self.ffmpeg_path, '-y', '-i', file]
            
            if self.task_type == "格式转码":
                cmd.extend(['-c:v', 'libx264', '-c:a', 'aac', out_path])
            elif self.task_type == "提取音频":
                out_path = os.path.join(self.output_dir, f"{name}_out.mp3")
                cmd.extend(['-vn', '-acodec', 'libmp3lame', out_path])
            elif self.task_type == "音频转码":
                bitrate = self.params.get('bitrate', '192k')
                if out_ext == '.mp3':
                    cmd.extend(['-vn', '-acodec', 'libmp3lame', '-b:a', bitrate, out_path])
                elif out_ext == '.aac':
                    cmd.extend(['-vn', '-acodec', 'aac', '-b:a', bitrate, out_path])
                elif out_ext == '.wav':
                    cmd.extend(['-vn', '-acodec', 'pcm_s16le', out_path])
                elif out_ext == '.flac':
                    cmd.extend(['-vn', '-acodec', 'flac', out_path])
                else:
                    cmd.extend(['-vn', '-b:a', bitrate, out_path])
            elif self.task_type == "体积压缩":
                cmd.extend(['-vf', 'scale=1280:-1', '-b:v', '1000k', out_path])
            elif self.task_type == "视频裁剪":
                cmd.extend(['-ss', self.params.get('start', '00:00:00'), '-t', self.params.get('duration', '10'), '-c', 'copy', out_path])
            elif self.task_type == "速度调整":
                spd = self.params.get('speed', '1.0')
                cmd.extend(['-vf', f'setpts={spd}*PTS', '-af', f'atempo={spd}', out_path])
            elif self.task_type == "添加水印":
                wm = self.params.get('watermark', '')
                cmd.extend(['-i', wm, '-filter_complex', 'overlay=W-w-10:H-h-10', out_path])

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore')
            for line in process.stdout:
                if 'frame=' in line or 'time=' in line or 'size=' in line:
                    self.log_signal.emit(f"  {line.strip()}")
            
            process.wait()
            if process.returncode == 0:
                self.log_signal.emit(f"  ✔ 成功: {os.path.basename(out_path)}\n")
            else:
                self.log_signal.emit(f"  ✖ 失败: {filename}\n")
                
        self.finished_signal.emit(True, "批量处理已完成。")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg-GUI")
        self.resize(1000, 700)
        self.files = []
        self.ffmpeg_path = "ffmpeg.exe"
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(48, 48, 48, 48)
        main_layout.setSpacing(48)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(24)
        
        title = QLabel("FFmpeg\nGUI.")
        title.setObjectName("title")
        title.setContentsMargins(0, 0, 0, 48)
        left_panel.addWidget(title)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(220)
        self.nav_list.addItems(["格式转码", "提取音频", "音频转码", "体积压缩", "视频裁剪", "速度调整", "添加水印"])
        self.nav_list.currentRowChanged.connect(self.switch_panel)
        left_panel.addWidget(self.nav_list)
        
        ffmpeg_layout = QHBoxLayout()
        self.ffmpeg_input = QLineEdit(self.ffmpeg_path)
        self.ffmpeg_input.setPlaceholderText("ffmpeg.exe 路径")
        btn_browse_ffmpeg = QPushButton("浏览")
        btn_browse_ffmpeg.setFixedWidth(80)
        btn_browse_ffmpeg.clicked.connect(self.browse_ffmpeg)
        ffmpeg_layout.addWidget(self.ffmpeg_input)
        ffmpeg_layout.addWidget(btn_browse_ffmpeg)
        left_panel.addLayout(ffmpeg_layout)
        left_panel.addStretch()
        main_layout.addLayout(left_panel, 1)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(32)

        file_header = QHBoxLayout()
        file_header.addWidget(QLabel("输入文件"))
        btn_add_files = QPushButton("添加文件")
        btn_add_files.clicked.connect(self.add_files)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.clear_files)
        file_header.addWidget(btn_add_files)
        file_header.addWidget(btn_clear)
        right_panel.addLayout(file_header)

        self.file_list = QListWidget()
        self.file_list.setFixedHeight(160)
        right_panel.addWidget(self.file_list)

        self.param_stack = QStackedWidget()
        self.build_param_panels()
        right_panel.addWidget(self.param_stack)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("输出目录"))
        self.out_dir_input = QLineEdit(os.getcwd())
        btn_browse_out = QPushButton("浏览")
        btn_browse_out.setFixedWidth(80)
        btn_browse_out.clicked.connect(self.browse_output)
        out_layout.addWidget(self.out_dir_input)
        out_layout.addWidget(btn_browse_out)
        right_panel.addLayout(out_layout)

        self.btn_execute = QPushButton("执行批量处理")
        self.btn_execute.setFixedHeight(56)
        self.btn_execute.clicked.connect(self.execute)
        right_panel.addWidget(self.btn_execute)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        right_panel.addWidget(self.log_area, 1)

        main_layout.addLayout(right_panel, 2)
        self.nav_list.setCurrentRow(0)

    def build_param_panels(self):
        p1 = QWidget()
        l1 = QFormLayout(p1)
        self.cb_format = QComboBox()
        self.cb_format.addItems([".mp4", ".mkv", ".avi", ".mov"])
        l1.addRow("目标格式", self.cb_format)
        self.param_stack.addWidget(p1)

        p2 = QWidget()
        l2 = QFormLayout(p2)
        l2.addRow(QLabel("提取 MP3 音频流，丢弃视频画面。"))
        self.param_stack.addWidget(p2)

        p3 = QWidget()
        l3 = QFormLayout(p3)
        self.cb_audio_format = QComboBox()
        self.cb_audio_format.addItems([".mp3", ".wav", ".flac", ".aac"])
        self.cb_audio_bitrate = QComboBox()
        self.cb_audio_bitrate.addItems(["128k", "192k", "256k", "320k"])
        l3.addRow("目标格式", self.cb_audio_format)
        l3.addRow("音频比特率", self.cb_audio_bitrate)
        self.param_stack.addWidget(p3)

        p4 = QWidget()
        l4 = QFormLayout(p4)
        l4.addRow(QLabel("缩放至 1280px 宽度，视频码率限制为 1000k。"))
        self.param_stack.addWidget(p4)

        p5 = QWidget()
        l5 = QFormLayout(p5)
        self.in_start = QLineEdit("00:00:00")
        self.in_duration = QLineEdit("10")
        l5.addRow("起始时间 (时:分:秒)", self.in_start)
        l5.addRow("持续时间 (秒)", self.in_duration)
        self.param_stack.addWidget(p5)

        p6 = QWidget()
        l6 = QFormLayout(p6)
        self.in_speed = QLineEdit("1.0")
        l6.addRow("速度倍率 (0.5 - 2.0)", self.in_speed)
        self.param_stack.addWidget(p6)

        p7 = QWidget()
        l7 = QFormLayout(p7)
        self.in_wm = QLineEdit()
        btn_wm = QPushButton("选择图片")
        btn_wm.setFixedWidth(100)
        btn_wm.clicked.connect(lambda: self.in_wm.setText(QFileDialog.getOpenFileName(self, "选择水印", "", "Images (*.png *.jpg)")[0]))
        wm_layout = QHBoxLayout()
        wm_layout.addWidget(self.in_wm)
        wm_layout.addWidget(btn_wm)
        l7.addRow("水印图片", wm_layout)
        self.param_stack.addWidget(p7)

    def switch_panel(self, index):
        self.param_stack.setCurrentIndex(index)

    def browse_ffmpeg(self):
        path = QFileDialog.getOpenFileName(self, "选择 FFmpeg", "", "Executable (*.exe)")[0]
        if path: self.ffmpeg_input.setText(path)

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path: self.out_dir_input.setText(path)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择媒体文件", "", "Media (*.mp4 *.mkv *.avi *.mov *.mp3 *.wav *.flac *.m4a)")
        for f in files:
            if f not in self.files:
                self.files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def clear_files(self):
        self.files.clear()
        self.file_list.clear()

    def execute(self):
        if not self.files:
            self.log_area.appendPlainText("✖ 错误：未选择任何文件。")
            return
        
        self.ffmpeg_path = self.ffmpeg_input.text() or "ffmpeg.exe"
        out_dir = self.out_dir_input.text()
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        task_type = self.nav_list.currentItem().text()
        params = {}
        
        if task_type == "格式转码":
            params['out_ext'] = self.cb_format.currentText()
        elif task_type == "音频转码":
            params['out_ext'] = self.cb_audio_format.currentText()
            params['bitrate'] = self.cb_audio_bitrate.currentText()
        elif task_type == "视频裁剪":
            params['start'] = self.in_start.text()
            params['duration'] = self.in_duration.text()
        elif task_type == "速度调整":
            params['speed'] = self.in_speed.text()
        elif task_type == "添加水印":
            params['watermark'] = self.in_wm.text()

        self.btn_execute.setEnabled(False)
        self.log_area.clear()
        self.log_area.appendPlainText(f"初始化批量任务: {task_type}\n")

        self.worker = FFmpegWorker(self.ffmpeg_path, self.files, out_dir, task_type, params)
        self.worker.log_signal.connect(self.log_area.appendPlainText)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.btn_execute.setEnabled(True)
        self.log_area.appendPlainText(f"\n{msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
