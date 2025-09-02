import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
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
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

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

# --- Кэш ---
def load_cache():
    cache_file = 'cache.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    cache_file = 'cache.json'
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        # git push
        try:
            if not os.path.exists('.git'):
                subprocess.run(['git', 'init'], check=True)
            git_repo = os.environ.get('GIT_REPO')
            git_token = os.environ.get('GIT_TOKEN')
            if git_token and git_repo:
                git_repo = git_repo.replace('https://', f'https://{git_token}@')
            if git_repo:
                subprocess.run(['git', 'remote', 'remove', 'origin'], capture_output=True)
                subprocess.run(['git', 'remote', 'add', 'origin', git_repo], check=True)
                subprocess.run(['git', 'config', '--global', 'user.name', os.environ.get('GIT_USER', 'floratvertransport-prog')], check=True)
                subprocess.run(['git', 'config', '--global', 'user.email', 'floratvertransport-prog@example.com'], check=True)
                subprocess.run(['git', 'add', cache_file], check=True)
                subprocess.run(['git', 'commit', '-m', 'Update cache.json'], check=True)
                subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        except Exception as e:
            st.warning(f"Git sync error: {e}")

    except Exception as e:
        st.error(f"Ошибка при сохранении кэша: {e}")

# --- Проверка ENV переменных ---
for key in ("GIT_REPO", "GIT_USER", "GIT_TOKEN", "ORS_API_KEY", "API_KEY"):
    if not os.environ.get(key):
        st.warning(f"Переменная окружения {key} не настроена.")

# --- Геокодер Яндекс ---
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={api_key}&geocode={address}&format=json"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
    except Exception:
        raise ValueError("Ошибка при обращении к Яндекс Геокодеру")

    try:
        pos = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
        lon, lat = map(float, pos.split(' '))
        return lat, lon
    except Exception:
        raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь').")

# --- Поиск ближайшей точки выхода ---
def find_nearest_exit_point(dest_lat, dest_lon):
    min_dist = float('inf')
    nearest_exit = None
    for exit_point in exit_points:
        dist = haversine(dest_lat, dest_lon, exit_point[1], exit_point[0])
        if dist < min_dist:
            min_dist = dist
            nearest_exit = exit_point
    return nearest_exit, min_dist

# --- Определение населённого пункта ---
def extract_locality(address):
    if 'тверь' in address.lower():
        return 'Тверь'
    cache = load_cache()
    for locality in cache.keys():
        if locality.lower() in address.lower():
            return locality
    return None

# --- Округление стоимости ---
def round_cost(cost):
    remainder = cost % 100
    if remainder <= 20:
        return (cost // 100) * 100
    else:
        return ((cost // 100) + 1) * 100

# --- Основной расчёт ---
async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, delivery_date=None, use_route_rate=False):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза")

    base_cost = cargo_prices[cargo_size]
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon)
    locality = extract_locality(address)
    st.session_state.locality = locality
    rate_per_km = 15 if use_route_rate else 32

    if locality and locality.lower() == 'тверь':
        return base_cost, 0, nearest_exit, locality, 0, "город", rate_per_km

    road_distance = dist_to_exit * 2 * 1.3
    total_cost = base_cost + road_distance * rate_per_km
    return round_cost(total_cost), dist_to_exit, nearest_exit, locality, road_distance, "haversine", rate_per_km

# --- Интерфейс ---
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")
api_key = os.environ.get("API_KEY")

with st.form(key="delivery_form"):
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки", value="Тверская область, ")
    delivery_date = st.date_input("Дата доставки", value=date.today(), format="DD.MM.YYYY")
    admin_password = st.text_input("Админ пароль (для отладки)", type="password")

    submit_button = st.form_submit_button("Рассчитать")

    if submit_button and address:
        try:
            dest_lat, dest_lon = geocode_address(address, api_key)
            result = asyncio.run(calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, delivery_date))
            cost, dist_to_exit, nearest_exit, locality, total_distance, source, rate_per_km = result
            st.success(f"Стоимость доставки: {cost} руб.")

            if admin_password == "admin123":
                st.write("---")
                st.write(f"Координаты адреса: lat={dest_lat}, lon={dest_lon}")
                st.write(f"Ближайшая точка выхода: {nearest_exit}")
                st.write(f"Расстояние до ближайшей точки выхода: {dist_to_exit:.2f} км")
                st.write(f"Извлечённый населённый пункт: {locality}")
                st.write(f"Источник расстояния: {source}")
                st.write(f"Дата доставки: {delivery_date.strftime('%d.%m.%Y')} ({delivery_date.strftime('%A')})")

        except ValueError as e:
            st.error(f"Ошибка: {e}")
        except Exception as e:
            st.error(f"Ошибка при расчёте: {e}")
