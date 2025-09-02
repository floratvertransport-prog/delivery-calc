import math
import requests
import streamlit as st
import os
import asyncio
import json
import subprocess
from datetime import date, datetime

# --- Настройка страницы ---
st.set_page_config(page_title="Калькулятор доставки (розница)", page_icon="favicon.png")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# --- Словарь цен за размер груза ---
cargo_prices = {
    "маленький": 500,
    "средний": 800,
    "большой": 1200
}

# --- Функция Haversine ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat, dlon = lat2_rad - lat1_rad, lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# --- Точки выхода из Твери ---
exit_points = [
    (36.055364, 56.795587),
    (35.871802, 56.808677),
    (35.804913, 56.831684),
    (36.020937, 56.850973),
    (35.797443, 56.882207),
    (35.932805, 56.902966),
    (35.804913, 56.831684)  # новая точка №7
]

# --- Рейсы и расписание ---
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

# --- Кэш ---
def load_cache():
    if os.path.exists("cache.json"):
        try:
            with open("cache.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open("cache.json", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        # git push
        try:
            if not os.path.exists(".git"):
                subprocess.run(["git", "init"], check=True)
            git_repo = os.environ.get("GIT_REPO")
            git_token = os.environ.get("GIT_TOKEN")
            if git_token and git_repo:
                git_repo = git_repo.replace("https://", f"https://{git_token}@")
            if git_repo:
                subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", git_repo], check=True)
                subprocess.run(["git", "config", "--global", "user.name", os.environ.get("GIT_USER", "floratvertransport-prog")], check=True)
                subprocess.run(["git", "config", "--global", "user.email", "floratvertransport-prog@example.com"], check=True)
                subprocess.run(["git", "add", "cache.json"], check=True)
                subprocess.run(["git", "commit", "-m", "Update cache.json"], check=True)
                subprocess.run(["git", "push", "origin", "main"], check=True)
        except Exception as e:
            st.warning(f"Git sync error: {e}")
    except Exception as e:
        st.error(f"Ошибка при сохранении кэша: {e}")

# --- Геокодер Яндекс ---
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={api_key}&geocode={address}&format=json"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
    except Exception:
        raise ValueError("Ошибка при обращении к Яндекс Геокодеру")
    try:
        pos = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        lon, lat = map(float, pos.split(" "))
        return lat, lon
    except Exception:
        raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь').")

# --- Определение рейса ---
def match_route(address, weekday_ru):
    for route, towns in ROUTES.items():
        if any(town in address for town in towns) and route in ROUTE_SCHEDULE.get(weekday_ru, []):
            return route
    return None

# --- Расчёт стоимости ---
def round_cost(cost):
    remainder = cost % 100
    return (cost // 100) * 100 if remainder <= 20 else ((cost // 100) + 1) * 100

async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, delivery_date, route_mode=False):
    base_cost = cargo_prices[cargo_size]
    weekday = delivery_date.strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье",
    }[weekday]

    nearest_exit, dist_to_exit = min(
        [(ep, haversine(dest_lat, dest_lon, ep[1], ep[0])) for ep in exit_points],
        key=lambda x: x[1]
    )

    rate_per_km = 32
    matched_route = match_route(address, weekday_ru)
    if matched_route and route_mode:
        rate_per_km = 15

    if "Тверь" in address:
        return base_cost, 0, nearest_exit, matched_route, 0, rate_per_km

    road_distance = dist_to_exit * 2 * 1.3
    total_cost = base_cost + road_distance * rate_per_km
    return round_cost(total_cost), dist_to_exit, nearest_exit, matched_route, road_distance, rate_per_km

# --- Интерфейс ---
st.title("Калькулятор доставки (розница)")
api_key = os.environ.get("API_KEY")

with st.form(key="delivery_form"):
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки", value="Тверская область, ")
    delivery_date = st.date_input("Дата доставки", value=date.today(), format="DD.MM.YYYY")
    admin_password = st.text_input("Админ пароль", type="password")
    submit_button = st.form_submit_button("Рассчитать")

    if submit_button and address:
        try:
            dest_lat, dest_lon = geocode_address(address, api_key)
            weekday_ru = delivery_date.strftime("%A")
            weekday_ru = {
                "Monday": "Понедельник",
                "Tuesday": "Вторник",
                "Wednesday": "Среда",
                "Thursday": "Четверг",
                "Friday": "Пятница",
                "Saturday": "Суббота",
                "Sunday": "Воскресенье",
            }[weekday_ru]

            matched_route = match_route(address, weekday_ru)
            route_mode = False
            if matched_route:
                if st.checkbox("Доставка по рейсу вместе с оптовыми заказами"):
                    if st.radio("Подтвердите:", ["Нет", "Да"]) == "Да":
                        route_mode = True

            cost, dist_to_exit, nearest_exit, route, road_distance, rate_per_km = asyncio.run(
                calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, delivery_date, route_mode)
            )

            st.success(f"Стоимость доставки: {cost} руб.")
            st.write(f"Дата: {delivery_date.strftime('%d.%m.%Y')} ({weekday_ru})")
            st.write(f"Километраж: {round(road_distance, 2)} км")
            st.write(f"Тариф: {rate_per_km} руб./км")
            st.write(f"Рейс: {route if route else 'Нет'}")

            if admin_password == "admin123":
                st.write("---")
                st.write(f"Координаты: lat={dest_lat}, lon={dest_lon}")
                st.write(f"Ближайшая точка выхода: {nearest_exit}")
                st.write(f"Расстояние до выхода: {dist_to_exit:.2f} км")

        except Exception as e:
            st.error(f"Ошибка: {e}")
