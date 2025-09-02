import sys
import os
import json
import requests
import subprocess
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QComboBox, QCalendarWidget, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt

# ========================
# Настройки
# ========================

ORS_API_KEY = os.getenv("ORS_API_KEY")
if not ORS_API_KEY:
    raise ValueError("ORS_API_KEY не найден! Установите его в Render → Environment Variables.")

CACHE_FILE = "cache.json"
GIT_BRANCH = "main"

GIT_REPO = os.getenv("GIT_REPO")
GIT_USER = os.getenv("GIT_USER")
GIT_TOKEN = os.getenv("GIT_TOKEN")

BASE_PRICES = {
    "маленький": 350,
    "средний": 700,
    "большой": 1000,
}

RATE_NORMAL = 32
RATE_ROUTE = 15

EXIT_POINTS = [
    (36.055364, 56.795587),  # Точка 1
    (35.871802, 56.808677),  # Точка 2
    (35.804913, 56.831684),  # Точка 3
    (36.020937, 56.850973),  # Точка 4
    (35.797443, 56.882207),  # Точка 5
    (35.932805, 56.902966),  # Точка 6
    (35.804913, 56.831684),  # Точка 7 (новая)
]

# ========================
# Рейсы
# ========================

ROUTES = {
    "Понедельник": {
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
            "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
            "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"
        ],
        "КШ_КЗ_КГ": ["Кашин", "Калязин", "Кесова Гора"],
    },
    "Вторник": {
        "КВ_КЛ": ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин"],
        "ЛШ_ШХ_ВК_РЗ": ["Руза", "Волоколамск", "Шаховская", "Лотошино"],
    },
    "Среда": {
        "КМ_ДБ": ["Дубна", "Кимры"],
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": ["Старица", "Ржев", "Зубцов"],
        "СЛЖ_ОСТ_КУВ": ["Кувшиново", "Осташков", "Селижарово", "Пено"],
    },
    "Четверг": {
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
            "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
            "Нелидово", "Оленино"
        ],
        "ТО_СП_ВВ_БГ_УД": ["Бологое"],
    },
    "Пятница": {
        "ТО_СП_ВВ_БГ_УД": ["Удомля", "Вышний Волочек", "Спирово", "Торжок", "Лихославль"],
        "РШ_МХ_ЛС_СД": ["Лесное", "Максатиха", "Рамешки"],
        "БК_СН_КХ_ВГ": ["Сандово", "Весьегонск", "Красный Холм", "Сонково", "Бежецк"],
    },
}

# ========================
# Вспомогательные функции
# ========================

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    git_push()

def git_push():
    try:
        if not all([GIT_REPO, GIT_USER, GIT_TOKEN]):
            print("GIT_REPO / GIT_USER / GIT_TOKEN не заданы в Environment Variables. Автопуш отключён.")
            return

        # Подменяем https://github.com/... на https://USER:TOKEN@github.com/...
        repo_url = GIT_REPO.replace(
            "https://", f"https://{GIT_USER}:{GIT_TOKEN}@"
        )

        subprocess.run(["git", "config", "user.email", f"{GIT_USER}@users.noreply.github.com"], check=True)
        subprocess.run(["git", "config", "user.name", GIT_USER], check=True)

        subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
        subprocess.run(["git", "add", CACHE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update cache"], check=True)
        subprocess.run(["git", "push", "origin", GIT_BRANCH], check=True)
        print("Кэш успешно запушен в GitHub.")
    except subprocess.CalledProcessError as e:
        print("Ошибка git push:", e)

def haversine(lon1, lat1, lon2, lat2):
    R = 6371
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def geocode_address(address):
    url = f"https://api.openrouteservice.org/geocode/search?api_key={ORS_API_KEY}&text={address}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "features" in data and data["features"]:
        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords
        return lat, lon
    return None, None

def calculate_distance(lat, lon):
    nearest_exit = min(EXIT_POINTS, key=lambda p: haversine(lon, lat, p[0], p[1]))
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    body = {"coordinates": [[nearest_exit[0], nearest_exit[1]], [lon, lat]]}
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    r = requests.post(url, json=body, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    distance_km = data["features"][0]["properties"]["segments"][0]["distance"] / 1000
    return distance_km * 2, nearest_exit

def detect_route(date: datetime, city: str):
    weekday = date.strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье",
    }[weekday]

    if weekday_ru in ROUTES:
        for route_name, towns in ROUTES[weekday_ru].items():
            if any(city.lower() in t.lower() for t in towns):
                return route_name
    return None

# ========================
# GUI
# ========================

class DeliveryApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Калькулятор доставки по Твери и области")

        self.cache = load_cache()

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Адрес доставки:"))
        self.address_input = QLineEdit()
        layout.addWidget(self.address_input)

        layout.addWidget(QLabel("Размер груза:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(BASE_PRICES.keys())
        layout.addWidget(self.size_combo)

        layout.addWidget(QLabel("Дата доставки:"))
        self.calendar = QCalendarWidget()
        self.calendar.setFirstDayOfWeek(Qt.Monday)
        self.calendar.setGridVisible(True)
        layout.addWidget(self.calendar)

        self.route_checkbox = QCheckBox("Доставка по рейсу вместе с оптовыми заказами")
        self.route_checkbox.setEnabled(False)
        layout.addWidget(self.route_checkbox)

        self.calc_button = QPushButton("Рассчитать")
        self.calc_button.clicked.connect(self.calculate)
        layout.addWidget(self.calc_button)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        self.setLayout(layout)

    def calculate(self):
        address = self.address_input.text().strip()
        size = self.size_combo.currentText()
        date = self.calendar.selectedDate().toPyDate()

        if not address:
            QMessageBox.warning(self, "Ошибка", "Введите адрес доставки")
            return

        if address in self.cache:
            data = self.cache[address]
            distance, exit_point = data["distance"], tuple(data["exit_point"])
        else:
            lat, lon = geocode_address(address)
            if not lat:
                QMessageBox.warning(self, "Ошибка", "Не удалось определить координаты")
                return
            distance, exit_point = calculate_distance(lat, lon)
            self.cache[address] = {"distance": distance, "exit_point": exit_point}
            save_cache(self.cache)

        city = address.split(",")[-1].strip()
        route = detect_route(datetime.combine(date, datetime.min.time()), city)

        if route:
            self.route_checkbox.setEnabled(True)
        else:
            self.route_checkbox.setEnabled(False)
            self.route_checkbox.setChecked(False)

        rate = RATE_ROUTE if self.route_checkbox.isChecked() else RATE_NORMAL
        base_price = BASE_PRICES[size]
        total = round(base_price + distance * rate)

        self.result_label.setText(
            f"Стоимость доставки: {total} руб.\n"
            f"Населённый пункт: {city}\n"
            f"Километраж (туда-обратно): {distance:.1f} км\n"
            f"Тариф: {rate} руб./км\n"
            f"Использован рейс: {'Да' if self.route_checkbox.isChecked() else 'Нет'}"
        )

# ========================
# Запуск
# ========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DeliveryApp()
    window.show()
    sys.exit(app.exec_())
