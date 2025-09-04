import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json
import subprocess
from datetime import date, datetime

# ====== НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ ======

# Локализация (fallback, если streamlit-i18n не установлен)
try:
    from streamlit_i18n import init, _
    init("ru")
except ImportError:
    def _(text): return text

# Вкладка
st.set_page_config(page_title="Калькулятор доставки (розница)", page_icon="favicon.png")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# Базовые тарифы
cargo_prices = {
    "маленький": 500,
    "средний": 800,
    "большой": 1200
}

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_server_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipify.org?format=json', timeout=5) as response:
                if response.status == 200:
                    return (await response.json()).get('ip', 'Неизвестно')
    except:
        return "Ошибка IP"
    return "Не удалось получить IP"

def load_cache():
    if os.path.exists("cache.json"):
        try:
            with open("cache.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    try:
        with open("cache.json", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        # GitHub sync
        if not os.path.exists(".git"):
            subprocess.run(["git", "init"], check=True)
        git_repo = os.environ.get("GIT_REPO")
        git_token = os.environ.get("GIT_TOKEN")
        if git_token and git_repo:
            git_repo = git_repo.replace("https://", f"https://{git_token}@")
        subprocess.run(["git", "config", "--global", "user.name", os.environ.get("GIT_USER", "floratvertransport-prog")], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "floratvertransport-prog@example.com"], check=True)
        subprocess.run(["git", "add", "cache.json"], check=True)
        subprocess.run(["git", "commit", "-m", "Update cache.json"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
    except Exception as e:
        st.warning(f"Ошибка GitHub sync: {e}")

# Геокодирование (Яндекс)
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={api_key}&geocode={address}&format=json"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise ValueError("Ошибка геокодера")
    try:
        pos = resp.json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        lon, lat = map(float, pos.split())
        return lat, lon
    except:
        raise ValueError("Адрес не найден")

# ORS расстояние
async def get_road_distance_ors(lat1, lon1, lat2, lon2, api_key):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {"coordinates": [[lon1, lat1], [lon2, lat2]], "units": "km"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers) as r:
            if r.status == 200:
                data = await r.json()
                return data["routes"][0]["summary"]["distance"]
            else:
                return haversine(lat1, lon1, lat2, lon2) * 1.3  # fallback

# Округление
def round_cost(cost):
    rem = cost % 100
    return (cost // 100) * 100 if rem <= 20 else ((cost // 100) + 1) * 100

# ====== ЗАГРУЗКА РЕЙСОВ ======
try:
    with open("routes.json", "r", encoding="utf-8") as f:
        routes = json.load(f)
except Exception as e:
    st.error(f"Ошибка загрузки routes.json: {e}")
    routes = []

# ====== ОСНОВНОЙ UI ======
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")

api_key = os.environ.get("API_KEY")
ors_api_key = os.environ.get("ORS_API_KEY")

with st.form("delivery_form"):
    cargo_size = st.selectbox("Размер груза", list(cargo_prices.keys()))
    address = st.text_input("Введите адрес доставки", value="Тверская область, ")
    delivery_date = st.date_input("Дата доставки", value=date.today(), format="DD.MM.YYYY")
    admin_password = st.text_input("Админ пароль", type="password")

    submit = st.form_submit_button("Рассчитать")

if submit and address:
    try:
        lat, lon = geocode_address(address, api_key)

        # --- Определяем тариф ---
        weekday = delivery_date.weekday()  # 0=Пн
        use_route = False
        matched_route = None
        deviation_limit_km = 10  # можно сделать настраиваемым в админке

        for r in routes:
            if weekday not in r["days"]:
                continue
            for stop in r["stops"]:
                dist = haversine(lat, lon, stop["lat"], stop["lon"])
                if dist <= deviation_limit_km:
                    use_route = True
                    matched_route = r["name"]
                    break

        rate_per_km = 15 if use_route else 32

        # --- Расстояние от ближайшей точки выхода ---
        min_exit = None
        min_dist = float("inf")
        for r in routes:
            d = haversine(lat, lon, r["exit"]["lat"], r["exit"]["lon"])
            if d < min_dist:
                min_dist = d
                min_exit = r["exit"]

        road_dist = asyncio.run(get_road_distance_ors(min_exit["lat"], min_exit["lon"], lat, lon, ors_api_key))
        total_dist = road_dist * 2
        base_cost = cargo_prices[cargo_size]
        total_cost = round_cost(base_cost + total_dist * rate_per_km)

        st.success(f"Стоимость доставки: {total_cost} руб.")
        st.write(f"Дата: {delivery_date.strftime('%d.%m.%Y')} ({delivery_date.strftime('%A')})")
        st.write(f"Километраж: {total_dist:.2f} км")
        st.write(f"Тариф: {rate_per_km} руб./км")
        st.write(f"Рейс: {matched_route if matched_route else 'Нет'}")
        st.write(f"Координаты: lat={lat}, lon={lon}")
        st.write(f"Ближайшая точка выхода: {min_exit}")
        st.write(f"Расстояние до выхода: {min_dist:.2f} км (по прямой)")

        # Обновляем кэш
        cache = load_cache()
        cache[address] = {"distance": total_dist, "exit_point": min_exit}
        save_cache(cache)

        # Админ-режим
        if admin_password == "admin123":
            st.subheader("Админ режим активирован")
            st.write("Текущий кэш:", cache)
            st.write("IP сервера:", asyncio.run(get_server_ip()))

    except Exception as e:
        st.error(f"Ошибка: {e}")
