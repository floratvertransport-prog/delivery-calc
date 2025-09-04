import streamlit as st
import requests
import json
import os
import math
from datetime import datetime
import subprocess

# --- Настройки ---
CACHE_FILE = "cache.json"
ROUTES_FILE = "routes.json"
ADMIN_PASSWORD = "admin123"

# --- Логотип и favicon ---
st.set_page_config(
    page_title="Калькулятор доставки (розница)",
    page_icon="favicon.ico",
    layout="centered",
)

st.image("logo.png", width=300)
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")

# --- Загрузка кэша ---
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# --- Загрузка рейсов ---
with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    routes = json.load(f)

# --- Функции ---
def geocode(address):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}&countrycodes=ru"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    data = resp.json()
    if not data:
        return None, None, None
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def find_nearest_exit(lat, lon, exits):
    nearest = None
    min_dist = float("inf")
    for ex in exits:
        dist = haversine(lat, lon, ex[1], ex[0])
        if dist < min_dist:
            min_dist = dist
            nearest = ex
    return nearest, min_dist

def push_to_git():
    try:
        subprocess.run(["git", "add", CACHE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update cache"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return "Git push: Success"
    except subprocess.CalledProcessError:
        return "Git push: Failed"

def is_on_route(lat, lon, weekday):
    """Проверяем, входит ли точка в маршрут рейса в выбранный день недели"""
    for route in routes:
        if weekday not in route["days"]:
            continue
        for point in route["points"]:
            dist = haversine(lat, lon, point[1], point[0])
            if dist <= 10:  # до 10 км от маршрута
                return route["name"]
    return None

# --- Интерфейс ---
address = st.text_input("Введите адрес доставки", value="Тверская область, ")

# Проверяем режим админа
admin_mode = False
show_admin = False

if address.strip().lower() == "/admin":
    show_admin = True
    address = ""  # очищаем адрес, чтобы не ломался геокодер

# Проверка параметра URL (?admin=1)
query_params = st.query_params
if "admin" in query_params and query_params["admin"] == "1":
    show_admin = True

# Ввод размера и даты
cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
date_obj = st.date_input("Выберите дату доставки", datetime.now())
date = date_obj.strftime("%Y/%m/%d")

# Определяем день недели (0=понедельник ... 6=воскресенье)
weekday = date_obj.weekday()
weekday_names = [
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
]

# --- Админ-панель ---
if show_admin:
    admin_password = st.text_input("Введите пароль для входа в админ-режим", type="password")
    if admin_password == ADMIN_PASSWORD:
        admin_mode = True
        st.success("Админ режим активирован")
        max_deviation = st.number_input(
            "Макс. отклонение адреса от графика рейса (по дороге), км",
            min_value=1.0, max_value=50.0, value=10.0
        )
    else:
        max_deviation = 10.0
else:
    max_deviation = 10.0

# --- Расчёт ---
if address.strip():
    lat, lon, display_name = geocode(address)
    if lat and lon:
        # Проверка рейса
        route_name = is_on_route(lat, lon, weekday)
        use_route_tariff = False
        if route_name:
            if st.checkbox("Доставка по рейсу вместе с оптовыми заказами"):
                confirm = st.radio("Вы уверены?", ["Нет", "Да"])
                if confirm == "Да":
                    use_route_tariff = True

        # Определяем тариф
        tariff = 15 if use_route_tariff else 32

        # Точки выхода
        exit_points = [
            (36.055364, 56.795587),
            (35.871802, 56.808677),
            (35.804913, 56.831684),
            (36.020937, 56.850973),
            (35.797443, 56.882207),
            (35.932805, 56.902966),
            (35.783293, 56.844247),
        ]
        nearest_exit, dist_exit = find_nearest_exit(lat, lon, exit_points)

        # Проверка — в пределах Твери
        in_tver = "Тверь" in display_name

        if in_tver:
            cost = 350
            st.markdown(f"""
                ### Результат
                Стоимость доставки: {cost:.0f} руб.  
                Дата: {date} ({weekday_names[weekday]})  
                В пределах адм. границ Твери — доплата за километраж не начисляется.  
                Координаты: lat={lat}, lon={lon}  
            """)
        else:
            distance = 2 * dist_exit  # туда-обратно
            base_price = 350 if cargo_size == "маленький" else 700 if cargo_size == "средний" else 1050
            extra = distance * tariff
            cost = base_price + extra
            st.markdown(f"""
                ### Результат
                Стоимость доставки: {cost:.1f} руб.  

                Дата: {date} ({weekday_names[weekday]})  
                Километраж: {distance:.2f} км  
                Тариф: {tariff} руб./км  
                Рейс: {route_name if route_name else "Нет"}  

                Координаты: lat={lat}, lon={lon}  
                Ближайшая точка выхода: {nearest_exit}  
                Расстояние до выхода: {dist_exit:.2f} км  
                Извлечённый населённый пункт: {display_name}  
            """)

        # Сохраняем в кэш
        cache[address] = {"distance": dist_exit, "exit_point": nearest_exit}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        # Git push (только если админ)
        if admin_mode:
            st.text(push_to_git())
    else:
        st.error("Не удалось определить координаты адреса")
