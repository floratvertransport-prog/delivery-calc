import os
import json
import math
import subprocess
import streamlit as st
from datetime import datetime
import calendar
import requests

# ====== НАСТРОЙКИ ======
CACHE_FILE = "cache.json"
BASE_PRICE_SMALL = 350
PRICE_PER_KM = 32
DISCOUNT_PRICE_PER_KM = 15

EXIT_POINTS = [
    (36.055364, 56.795587),  # Точка 1
    (35.871802, 56.808677),  # Точка 2
    (35.804913, 56.831684),  # Точка 3
    (36.020937, 56.850973),  # Точка 4
    (35.797443, 56.882207),  # Точка 5
    (35.932805, 56.902966),  # Точка 6
    (35.804913, 56.831684),  # Точка 7
]

# ====== РЕЙСЫ ======
ROUTES = {
    "КВ_КЛ": ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин"],
    "ЛШ_ШХ_ВК_РЗ": ["Руза", "Волоколамск", "Шаховская", "Лотошино"],
    "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": ["Великие Луки", "Жарковский", "Торопец", "Западная Двина",
                                       "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"],
    "КМ_ДБ": ["Дубна", "Кимры"],
    "ТО_СП_ВВ_БГ_УД": ["Бологое", "Вышний Волочек", "Спирово", "Торжок", "Лихославль", "Удомля"],
    "РШ_МХ_ЛС_СД": ["Сандово", "Лесное", "Максатиха", "Рамешки"],
    "БК_СН_КХ_ВГ": ["Весьегонск", "Красный Холм", "Сонково", "Бежецк"],
    "КШ_КЗ_КГ": ["Кесова Гора", "Калязин", "Кашин"],
    "СЛЖ_ОСТ_КУВ": ["Кувшиново", "Осташков", "Селижарово"]
}

ROUTE_SCHEDULE = {
    "Понедельник": ["РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "КШ_КЗ_КГ"],
    "Вторник": ["КВ_КЛ", "ЛШ_ШХ_ВК_РЗ"],
    "Среда": ["КМ_ДБ", "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "СЛЖ_ОСТ_КУВ"],
    "Четверг": ["РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "ТО_СП_ВВ_БГ_УД"],
    "Пятница": ["ТО_СП_ВВ_БГ_УД", "РШ_МХ_ЛС_СД", "БК_СН_КХ_ВГ"],
}

# ====== ЗАГРУЗКА КЭША ======
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    repo = os.getenv("GIT_REPO")
    user = os.getenv("GIT_USER")
    token = os.getenv("GIT_TOKEN")
    if repo and user and token:
        try:
            subprocess.run(["git", "add", CACHE_FILE], check=True)
            subprocess.run(["git", "commit", "-m", "Update cache"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
        except Exception as e:
            st.warning(f"Ошибка при синхронизации с GitHub: {e}")

# ====== ВСПОМОГАТЕЛЬНЫЕ ======
def haversine(lon1, lat1, lon2, lat2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def geocode(address):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}&accept-language=ru"
    resp = requests.get(url).json()
    if resp:
        return float(resp[0]["lat"]), float(resp[0]["lon"]), resp[0]["display_name"]
    return None, None, None

def is_in_tver(address_name):
    return "Тверь" in address_name

# ====== STREAMLIT UI ======
st.set_page_config(page_title="Калькулятор доставки", page_icon="🚚")

st.title("Калькулятор стоимости доставки по Твери и области")

address = st.text_input("Введите адрес доставки")
cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])

# Русифицированный календарь
today = datetime.today()
cal = calendar.Calendar(firstweekday=0)  # Понедельник
year, month = today.year, today.month
st.write("### Выберите дату доставки")
date = st.date_input("Дата доставки", today, format="DD.MM.YYYY")

if st.button("Рассчитать"):
    if not address:
        st.error("Введите адрес доставки!")
    else:
        lat, lon, display_name = geocode(address)
        if not lat:
            st.error("Адрес не найден")
        else:
            if is_in_tver(display_name):
                distance = 0
            else:
                nearest_exit = min(EXIT_POINTS, key=lambda p: haversine(lon, lat, p[0], p[1]))
                distance = haversine(lon, lat, nearest_exit[0], nearest_exit[1]) * 2

            weekday = date.strftime("%A")
            weekday_ru = {
                "Monday": "Понедельник",
                "Tuesday": "Вторник",
                "Wednesday": "Среда",
                "Thursday": "Четверг",
                "Friday": "Пятница",
                "Saturday": "Суббота",
                "Sunday": "Воскресенье"
            }[weekday]

            matched_route = None
            for route, towns in ROUTES.items():
                if any(town in display_name for town in towns) and route in ROUTE_SCHEDULE.get(weekday_ru, []):
                    matched_route = route
                    break

            price_per_km = PRICE_PER_KM
            if matched_route:
                if st.checkbox("Доставка по рейсу вместе с оптовыми заказами"):
                    confirm = st.radio("Вы уверены?", ["Нет", "Да"])
                    if confirm == "Да":
                        price_per_km = DISCOUNT_PRICE_PER_KM

            total = BASE_PRICE_SMALL + distance * price_per_km
            st.success(f"Стоимость доставки: {round(total, 2)} руб.")
            st.write(f"Адрес: {display_name}")
            st.write(f"Дата: {date.strftime('%d.%m.%Y')} ({weekday_ru})")
            st.write(f"Километраж: {round(distance, 2)} км")
            st.write(f"Использован рейс: {matched_route if matched_route else 'Нет'}")
