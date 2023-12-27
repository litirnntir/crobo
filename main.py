import datetime
import json
import os
import subprocess
import sys
import time
import requests
from PyQt6 import QtCharts

from PyQt6 import QtCore

from PyQt6.QtGui import QPixmap, QPalette, QBrush, QFont
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QRadioButton, QTimeEdit,
                             QVBoxLayout, QHBoxLayout, QMessageBox, QLabel, QTableWidget, QHeaderView,
                             QAbstractItemView, QTableWidgetItem, QFileDialog)
from PyQt6.QtCore import QTimer, QTime


# Сборка:  pyinstaller main.spec

# Абсолютный путь
def resource_path(relative_path: str) -> str:
    user_dir = os.path.expanduser("~")
    app_dir = os.path.join(user_dir, "Crono")
    settings_file = os.path.join(app_dir, relative_path)
    return settings_file


def message(text="", icon_path=None, title=""):
    msg = QMessageBox()
    if icon_path:
        pixmap = QPixmap(icon_path)
        msg.setIconPixmap(pixmap)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.exec()


def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def get_active_app_name():
    script = """
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell
    return frontApp
    """
    output = subprocess.check_output(["osascript", "-e", script])
    return output.strip().decode("utf-8")


class TimeTracker(QWidget):
    def __init__(self):
        super().__init__()

        # установка шрифта для всех элементов
        font = QFont("Point")
        font.setPointSize(20)
        self.setFont(font)
        # Путь до файла
        self.path_write = resource_path("stats.txt")
        # Фон
        background_image = resource_path("background.png")
        pix = QPixmap(background_image)
        pal = QPalette()
        pal.setBrush(self.backgroundRole(), QBrush(pix))
        self.setPalette(pal)
        # заголовок, размер и положение окна
        self.setWindowTitle('Хронометраж')
        self.setFixedSize(800, 600)
        # Общее время
        self.label_total_time = QLabel("Прошло времени: 00:00:00")
        self.label_total_time.setStyleSheet("color: white; font-size: 22px")
        self.label_total_time.setFixedSize(400, 30)
        self.label_directory = QLabel(f"Путь: {self.path_write}")
        self.label_directory.setStyleSheet("color: white; font-size: 18px")
        self.label_directory.setFixedSize(300, 30)
        # виджеты для кнопок, переключателей, таймера и списка
        self.start_button = QPushButton('Старт')
        self.start_button.setFixedSize(350, 40)
        self.pause_button = QPushButton('Пауза')
        self.pause_button.setFixedSize(350, 40)
        self.stop_button = QPushButton('Стоп')
        self.stop_button.setFixedSize(350, 40)
        self.path_button = QPushButton('Путь для отчета')
        self.path_button.setFixedSize(350, 40)
        self.show_diagram_button = QPushButton('Показать диаграмму')
        self.show_diagram_button.setFixedSize(350, 40)
        self.report_button = QPushButton('Отчет')
        self.report_button.setEnabled(False)
        self.report_button.setFixedSize(350, 40)
        self.all_time_radio = QRadioButton('Без лимита')
        self.all_time_radio.setStyleSheet("color: white; font-size: 22px;")
        self.all_time_radio.setFixedSize(350, 40)
        self.timer_radio = QRadioButton('С лимитом')
        self.timer_radio.setStyleSheet("color: white; font-size: 22px;")
        self.timer_radio.setFixedSize(350, 40)
        self.time_edit = QTimeEdit()
        self.time_edit.setFixedSize(350, 40)
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(2)
        self.process_table.setHorizontalHeaderLabels(["Приложение", "Время"])
        self.process_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.process_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.process_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pause_button.setEnabled(False)
        self.time_edit.setEnabled(False)
        self.timer = QTimer()
        self.processes = {}  # процессы и время
        self.current_process = None
        self.start_time = None
        self.pause_time = None
        self.mode = 'All time'
        self.limit = None
        self.total_time = 0
        with open(resource_path("config.json"), "r") as f:
            data = json.load(f)
        self.TOKEN = data["TOKEN"]
        self.chat_id = data["chat_id"]

        # сигналы и слоты для обработки событий
        self.start_button.clicked.connect(self.start)
        self.pause_button.clicked.connect(self.pause)
        self.show_diagram_button.clicked.connect(self.show_diagram)
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        self.report_button.clicked.connect(self.report)
        self.path_button.clicked.connect(self.select_path)

        # сигналы и слоты для таймера и переключателя
        self.all_time_radio.toggled.connect(self.set_mode)
        self.all_time_radio.setChecked(True)
        self.timer_radio.toggled.connect(self.set_mode)
        self.time_edit.timeChanged.connect(self.set_limit)
        self.timer.timeout.connect(self.update)

        # макеты для размещения виджетов
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()
        self.main_layout = QHBoxLayout()

        # виджеты в макетах
        self.left_layout.addWidget(self.label_total_time)
        self.left_layout.addWidget(self.start_button)
        self.left_layout.addWidget(self.pause_button)
        self.left_layout.addWidget(self.stop_button)
        self.left_layout.addWidget(self.path_button)
        self.left_layout.addWidget(self.show_diagram_button)
        self.left_layout.addWidget(self.label_directory)
        self.left_layout.addWidget(self.report_button)
        self.left_layout.addWidget(self.all_time_radio)
        self.left_layout.addWidget(self.timer_radio)
        self.left_layout.addWidget(self.time_edit)
        self.right_layout.addWidget(self.process_table)
        self.main_layout.addLayout(self.left_layout)
        self.main_layout.addLayout(self.right_layout)

        # главный макет для окна
        self.setLayout(self.main_layout)
        self.show()

    def show_diagram(self):
        for app, time in self.processes.items():
            bar = QtCharts.QBarSet(app)
            bar.append(time / self.sum_values() * 100)
            self.series.append(bar)
        self.chart.addSeries(self.series)
        self.axis_x.setTitleText("Приложения")
        self.axis_y.setTitleText("Процент использования")
        self.chart.addAxis(self.axis_x, QtCore.Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.axis_x)
        self.series.attachAxis(self.axis_y)
        self.chart.setTitle("Время, проведенное в приложениях")
        self.chart_widget.setChart(self.chart)
        self.chart_window.setCentralWidget(self.chart_widget)
        self.chart_window.show()

    def select_path(self):
        # создаем диалоговое окно для выбора папки
        dialog = QFileDialog(self)
        # устанавливаем заголовок и режим выбора папки
        dialog.setWindowTitle('Выберите путь')
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        # если пользователь нажал кнопку ОК, то получаем выбранный путь
        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            path = dialog.selectedFiles()[0]
            # обновляем метку с выбранным путем
            self.path_write = path + "/stats.txt"
            # здесь можно добавить код для загрузки отчета в выбранную папку
        self.label_directory.setText(f"Путь: {self.path_write}")

    # Метод для обработки переключения режима работы
    def set_mode(self):
        radio = self.sender()
        if radio.isChecked():
            self.mode = radio.text()
            if self.mode == 'С лимитом':
                self.time_edit.setEnabled(True)
                self.set_limit(self.time_edit.time())
            else:
                self.time_edit.setEnabled(False)
                self.limit = None

    # Метод для установки лимита времени
    def set_limit(self, time_limit):
        self.limit = time_limit.hour() * 3600 + time_limit.minute() * 60 + time_limit.second()

    def sum_values(self):
        total = 0
        for value in self.processes.values():
            total += value
        return total

    def send_to_telegram(self):
        message('Статистика успешно загружена', icon_path=None, title="Успешно")
        document = open(self.path_write, "rb")  # Открыть файл со статистикой
        url = f"https://api.telegram.org/bot{self.TOKEN}/sendDocument?chat_id={self.chat_id}"  # Сформировать URL для отправки документа
        data = {
            f"caption": f"Cтатистика за последние: {format_time(self.sum_values())}"}  # Добавить подпись к документу
        requests.post(url, data=data, files={"document": document})  # Отправить POST-запрос с документом

    def report(self):
        self.current_process = None

        with open(self.path_write, "w") as f:
            f.write(f"Общее время: {format_time(self.total_time)}\n\n")
            f.write(f"Время в приложениях:\n")
            for app, time in self.processes.items():
                f.write(f"{{{app}: {str(datetime.timedelta(seconds=time))}}}\n")
        self.send_to_telegram()

    def start(self):
        self.set_mode()
        self.report_button.setEnabled(True)
        self.timer_radio.setEnabled(False)
        self.all_time_radio.setEnabled(False)
        self.time_edit.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.timer.start(1000)
        message('Считывание процессов начато', icon_path=None, title="Успешно")

    def pause(self):
        self.pause_button.setEnabled(False)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.report_button.setEnabled(True)
        self.current_process = None
        self.timer.stop()
        self.pause_time = QTime.currentTime()

    # Метод для обработки нажатия на кнопку Стоп
    def stop(self):
        self.report()
        self.report_button.setEnabled(False)
        self.timer_radio.setEnabled(True)
        self.all_time_radio.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
        self.timer.stop()
        self.current_process = None
        self.current_process = None
        self.start_time = None
        self.total_time = 0
        self.processes = {}
        self.clear_table()

        message('Считывание процессов завершено', icon_path=None, title="Успешно")

    def add_to_table(self):
        self.process_table.setRowCount(len(self.processes))
        row = 0
        for app, time in self.processes.items():
            app_item = QTableWidgetItem(app)
            time_item = QTableWidgetItem(str(datetime.timedelta(seconds=time)))
            self.process_table.setItem(row, 0, app_item)
            self.process_table.setItem(row, 1, time_item)
            row += 1

    def clear_table(self):
        row_count = self.process_table.rowCount()
        for i in range(row_count - 1, -1, -1):
            self.process_table.removeRow(i)

    def add_time_stats(self, app_name):
        self.add_to_table()
        if app_name in self.processes:
            self.processes[app_name] += 1
        else:
            self.processes[app_name] = 1

    # Главный метод обработки
    def update(self):
        active_process = get_active_app_name()
        self.add_time_stats(active_process)
        self.current_process = get_active_app_name()
        if self.mode == 'С лимитом' and self.total_time >= self.limit:
            self.stop()
        self.total_time += 1
        self.label_total_time.setText("Прошло времени: " + (time.strftime("%H:%M:%S", time.gmtime(self.total_time))))


app = QApplication(sys.argv)
window = TimeTracker()
window.show()
sys.exit(app.exec())
