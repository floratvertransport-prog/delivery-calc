# delivery_app.py
import os
import json
import math
from datetime import datetime
import subprocess

import streamlit as st
import requests

# ---------- Константы / файлы ----------
CACHE_FILE = "cache.json"
ROUTES_FILE = "routes.json"
ADMIN_PASSWORD = "admin123"  # поменяйте

# ---------- Favicon до первого вызова Streamlit ----------
page_icon = "favicon.png" if os.path.exists("favicon.png") else "🧭"

st.set_page_config(
    page_title="Калькулятор доставки (розница)",
    page_icon=page_icon,
    layout="centered"
)

# ---------- Шапка с логотипом по центру ----------
with st.container():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=300)
        else:
            st.markdown(
                "<h1 style='text-align:center;margin:0;'>Калькулятор доставки</h1>",
                unsafe_allow_html=True
            )

st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")
st.caption("Как открыть админку: набери **/admin** в поле «Поиск адреса» или добавь к URL `?admin=1`. Затем введи пароль.")

# ---------- Работа с кэшем ----------
def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_cache(cache_obj: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

cache = load_cache()

# ---------- Загрузка routes.json ----------
def load_routes():
    try:
        with open(ROUTES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        st.error(f"Ошибка чтения {ROUTES_FILE}: {e}")
        return []

    routes_list = []
    # если словарь → берём values()
    iterable = raw.values() if isinstance(raw, dict) else raw

    for r in iterable:
        if not isinstance(r, dict):
            continue
        name = r.get("name", "Рейс")
        days = [int(x) for x in r.get("days", []) if isinstance(x, int) or str(x).isdigit()]
        points = []
        for p in r.get("points", []):
            try:
                lon, lat = float(p[0]), float(p[1])
                points.append([lon, lat])
            except Exception:
                continue
        if points:
            routes_list.append({"name": name, "days": days, "points": points})

    return routes_list

routes = load_routes()

# ---------- Гео и расчёты ----------
def geocode(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"format": "json", "q": address, "countrycodes": "ru", "limit": 1}
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": "DeliveryCalc/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None, None, None
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
    except Exception:
        return None, None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def find_nearest_exit(lat, lon, exits):
    nearest, min_dist = None, float("inf")
    for ex in exits:
        dist = haversine(lat, lon, ex[1], ex[0])
        if dist < min_dist:
            min_dist, nearest = dist, ex
    return nearest, min_dist

def is_on_route(lat, lon, weekday, max_km, routes_list):
    for route in routes_list:
        if weekday not in route["days"]:
            continue
        for p in route["points"]:
            dist = haversine(lat, lon, p[1], p[0])
            if dist <= max_km:
                return route["name"]
    return None

def push_to_git():
    try:
        subprocess.run(["git", "add", CACHE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update cache"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return "Git push: Success"
    except Exception as e:
        return f"Git push: Failed ({e})"

# ---------- UI ----------
address = st.text_input("Поиск адреса", value="Тверская область, ")

# Админка
admin_requested = address.strip().lower() == "/admin"
url_params = {}
try:
    url_params = st.query_params
except Exception:
    pass
param_admin = str(url_params.get("admin", "0")) == "1"

show_admin = admin_requested or param_admin
admin_mode = False

address_for_geocode = address if not admin_requested else ""

cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])

today = datetime.now().date()
date_val = st.date_input("Выберите дату доставки", value=today)
date_str = datetime.combine(date_val, datetime.min.time()).strftime("%d.%m.%Y")
weekday = date_val.weekday()
weekday_names = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]

max_deviation_km = 10.0
if show_admin:
    pwd = st.text_input("Пароль администратора", type="password")
    if pwd == ADMIN_PASSWORD:
        admin_mode = True
        st.success("Админ-режим активирован")
        max_deviation_km = st.number_input(
            "Максимальное отклонение от маршрута (км)",
            min_value=1.0, max_value=50.0, value=10.0
        )
    else:
        st.info("Введите правильный пароль.")

# ---------- Расчёт ----------
if address_for_geocode.strip():
    lat, lon, display_name = geocode(address_for_geocode)
    if lat is not None and lon is not None:
        route_name = is_on_route(lat, lon, weekday, max_deviation_km, routes)

        use_route_tariff = False
        if route_name:
            if st.checkbox("Доставка по рейсу вместе с оптовыми заказами"):
                confirm = st.radio("Подтвердите выбор", ["Нет", "Да"], horizontal=True)
                use_route_tariff = (confirm == "Да")

        tariff = 15 if use_route_tariff else 32

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

        in_tver = "Тверь" in (display_name or "")

        if in_tver:
            cost = 350
            st.markdown(
                f"### Результат\n"
                f"**Стоимость доставки:** {cost:.0f} ₽  \n"
                f"**Дата:** {date_str} ({weekday_names[weekday]})  \n"
                f"В пределах адм. границ Твери — доплата не начисляется.  \n"
                f"**Координаты:** lat={lat:.6f}, lon={lon:.6f}"
            )
        else:
            distance_km = 2 * dist_exit
            base_price = 350 if cargo_size == "маленький" else 700 if cargo_size == "средний" else 1050
            extra = distance_km * tariff
            cost = base_price + extra

            st.markdown(
                f"### Результат\n"
                f"**Стоимость доставки:** {cost:.1f} ₽  \n"
                f"**Дата:** {date_str} ({weekday_names[weekday]})  \n"
                f"**Километраж:** {distance_km:.2f} км  \n"
                f"**Тариф:** {tariff} ₽/км  \n"
                f"**Рейс:** {route_name if route_name else 'Нет'}  \n"
                f"**Координаты:** lat={lat:.6f}, lon={lon:.6f}  \n"
                f"**Ближайшая точка выхода:** {nearest_exit}  \n"
                f"**Расстояние до выхода:** {dist_exit:.2f} км  \n"
                f"**Извлечённый адрес:** {display_name}"
            )

        cache[address_for_geocode] = {"nearest_exit": nearest_exit, "dist_to_exit": dist_exit}
        save_cache(cache)

        if admin_mode:
            st.caption(push_to_git())
    else:
        st.error("Не удалось определить координаты адреса.")
elif admin_requested:
    st.info("Админ-режим активирована. Введите пароль выше.")
