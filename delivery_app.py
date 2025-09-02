import sys
import os
import json
import subprocess
import locale
import requests
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCalendarWidget, QMessageBox, QCheckBox
)
from PyQt5.QtCore import QDate, Qt


# --------------------------
# Константы
# --------------------------
CACHE_FILE = "cache.json"
GIT_REPO = "https://******@github.com/floratvertransport-prog/delivery-calc.git"
GIT_BRANCH = "main"

BASE_PRICE_SMALL = 350
BASE_PRICE_MEDIUM = 700
BASE_PRICE_LARGE = 1000

TARIFF_DEFAULT = 32
TARIFF_RACE = 15

EXIT_POINTS = [
    (36.055364, 56.795587),
    (35.871802, 56.808677),
    (35.804913, 56.831684),
    (36.020937, 56.850973),
    (35.797443, 56.882207),
    (35.932805, 56.902966),
    (35.804913, 56.831684)  # новая точка №7
]

# --------------------------
# Рейсы по дням недели
# --------------------------
RACES = {
    "Понедельник": {
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
            "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
            "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"
        ],
        "КШ_КЗ_КГ": ["Кашин", "Калязин", "Кесова Гора"]
    },
    "Вторник": {
        "КВ_КЛ": ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин"],
        "ЛШ_ШХ_ВК_РЗ": ["Руза", "Волоколамск", "Шаховская", "Лотошино"]
    },
    "Среда": {
        "КМ_ДБ": ["Дубна", "Кимры"],
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": ["Старица", "Ржев", "Зубцов"],
        "СЛЖ_ОСТ_КУВ": ["Кувшиново", "Осташков", "Селижарово", "Пено"]
    },
    "Четверг": {
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
            "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
            "Нелидово", "Оленино"
        ],
        "ТО_СП_ВВ_БГ_УД": ["Бологое"]
    },
    "Пятница": {
        "ТО_СП_ВВ_БГ_УД": ["Удомля", "Вышний Волочек", "Спирово", "Торжок", "Лихославль"],
        "РШ_МХ_ЛС_СД": ["Лесное", "Максатиха", "Рамешки"],
        "БК_СН_КХ_ВГ": ["Сандово", "Весьегонск", "Красный Холм", "Сонково", "Бежецк"]
    }
}


# --------------------------
# Функции
# --------------------------

def haversine(coord1, coord2):
    """Расстояние между двумя координатами по прямой"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    R = 6371.0
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


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
        subprocess.run(["git", "add", CACHE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update cache"], check=True)
        subprocess.run(["git", "push", "origin", GIT_BRANCH], check=True)
    except Exception as e:
        print("Git push error:", e)


def extract_locality(address):
    """Определяем населённый пункт по адресу"""
    parts = address.split(",")
    if len(parts) > 1:
        return parts[1].strip()
    return address.strip()


def is_in_tver(locality):
    """Проверка, находится ли адрес в черте Твери"""
    return locality.lower() in ["тверь", "г.Тверь", "г. тверь"]


def get_nearest_exit(coord):
    min_dist = float("inf")
    best = EXIT_POINTS[0]
    for p in EXIT_POINTS:
        d = haversine(coord, p)
        if d < min_dist:
            min_dist = d
            best = p
    return best


def find_race(locality, weekday):
    """Определяем рейс"""
    races_today = RACES.get(weekday, {})
    for race_name, towns in races_today.items():
        if locality in towns:
            return race_name
    return None


# --------------------------
# GUI
# --------------------------
class DeliveryApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Калькулятор доставки по Твери и области")
        self.resize(500, 400)

        self.cache = load_cache()

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Введите адрес доставки:"))
        self.address_input = QLineEdit()
        layout.addWidget(self.address_input)

        layout.addWidget(QLabel("Размер груза:"))
        self.size_box = QComboBox()
        self.size_box.addItems(["маленький", "средний", "большой"])
        layout.addWidget(self.size_box)

        layout.addWidget(QLabel("Выберите дату доставки:"))
        self.calendar = QCalendarWidget()
        self.calendar.setFirstDayOfWeek(Qt.Monday)
        locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
        layout.addWidget(self.calendar)

        self.race_checkbox = QCheckBox("Доставка по рейсу вместе с оптовыми заказами")
        self.race_checkbox.setVisible(False)
        layout.addWidget(self.race_checkbox)

        self.calc_button = QPushButton("Рассчитать")
        self.calc_button.clicked.connect(self.calculate)
        layout.addWidget(self.calc_button)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        self.setLayout(layout)

    def calculate(self):
        address = self.address_input.text().strip()
        size = self.size_box.currentText()
        date = self.calendar.selectedDate().toPyDate()
        weekday = date.strftime("%A")
        weekday_ru = date.strftime("%A")

        locality = extract_locality(address)

        if is_in_tver(locality):
            price = {
                "маленький": BASE_PRICE_SMALL,
                "средний": BASE_PRICE_MEDIUM,
                "большой": BASE_PRICE_LARGE
            }[size]
            self.result_label.setText(f"Адрес в Твери. Стоимость: {price} руб.")
            return

        # Поиск рейса
        race = find_race(locality, date.strftime("%A"))
        if race:
            self.race_checkbox.setVisible(True)
            tariff = TARIFF_RACE if self.race_checkbox.isChecked() else TARIFF_DEFAULT
        else:
            self.race_checkbox.setVisible(False)
            tariff = TARIFF_DEFAULT

        # Дистанция (заглушка, можно заменить API)
        if locality in self.cache:
            distance = self.cache[locality]["distance"]
        else:
            # заглушка — ставим 50 км
            distance = 50
            self.cache[locality] = {"distance": distance}
            save_cache(self.cache)

        base_price = {
            "маленький": BASE_PRICE_SMALL,
            "средний": BASE_PRICE_MEDIUM,
            "большой": BASE_PRICE_LARGE
        }[size]

        total = base_price + distance * tariff
        self.result_label.setText(
            f"Населённый пункт: {locality}\n"
            f"Километраж: {distance:.2f} км\n"
            f"Тариф: {tariff} руб/км\n"
            f"Стоимость: {round(total)} руб."
        )


# --------------------------
# Запуск приложения
# --------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DeliveryApp()
    window.show()
    sys.exit(app.exec_())
