import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json
import subprocess
from datetime import date, datetime

# Установка заголовка вкладки
st.set_page_config(page_title="Флора калькулятор (розница)", page_icon="favicon.png")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# Функция Haversine
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

# Асинхронная функция получения IP сервера
async def get_server_ip():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.ipify.org?format=json") as response:
            data = await response.json()
            return data.get("ip", "Не удалось определить IP")

# Асинхронная функция получения расстояния через ORS
async def get_road_distance_ors(start_lat, start_lon, end_lat, end_lon, api_key):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key}
    params = {
        "start": f"{start_lon},{start_lat}",
        "end": f"{end_lon},{end_lat}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            data = await response.json()
            if data.get("features"):
                return data["features"][0]["properties"]["segments"][0]["distance"] / 1000  # в км
            return None

# Загрузка точек выхода и маршрутов из routes.json
def load_routes():
    try:
        with open("routes.json", "r") as f:
            data = json.load(f)
            exit_points = data.get("exit_points", [])
            route_groups = data.get("route_groups", {})
            return exit_points, route_groups
    except FileNotFoundError:
        st.error("Файл routes.json не найден. Убедитесь, что он загружен из репозитория.")
        return [], {}

# Функция геокодирования
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?format=json&geocode={address}&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    if data["response"]["GeoObjectCollection"]["featureMember"]:
        coords = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        return tuple(map(float, coords.split()))
    raise ValueError("Адрес не найден")

# Функция расчёта стоимости доставки
async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key, delivery_date):
    today = date.today()
    day_of_week = today.weekday()
    min_distance = float('inf')
    nearest_exit = None
    locality = None

    exit_points, route_groups = load_routes()
    if not exit_points:
        st.error("Точки выхода не загружены.")
        return None, None, None, None, None, None, None

    # Поиск ближайшей точки выхода
    for i, (exit_lat, exit_lon) in enumerate(exit_points):
        distance = haversine(dest_lat, dest_lon, exit_lat, exit_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_exit = i

    # Проверка маршрута для дня недели
    routes = route_groups.get(day_of_week, {})
    for route_name, route_points in routes.items():
        for point in route_points:
            point_lat, point_lon = point["coords"]
            distance_to_point = haversine(dest_lat, dest_lon, point_lat, point_lon)
            if distance_to_point < 5:  # Радиус 5 км
                locality = point["name"]
                break
        if locality:
            break

    # Расчёт расстояния через ORS
    total_distance = await get_road_distance_ors(exit_points[nearest_exit][0], exit_points[nearest_exit][1], dest_lat, dest_lon, routing_api_key)
    if total_distance is None:
        total_distance = min_distance  # Фallback на Haversine

    # Определение тарифа
    base_cost = {"маленький": 350, "средний": 500, "большой": 800}.get(cargo_size, 350)
    rate_per_km = 50  # Примерный тариф
    cost = base_cost + (total_distance * rate_per_km)
    method = "ORS" if total_distance != min_distance else "Haversine"

    return cost, min_distance, nearest_exit, locality, total_distance, method, rate_per_km

# Основной интерфейс
st.title("Калькулятор доставки Флора")

# Поля ввода
cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
address = st.text_input("Адрес доставки")
delivery_date = st.date_input("Дата доставки", value=date.today())
api_key = os.getenv("API_KEY")
routing_api_key = os.getenv("ORS_API_KEY")

# Секция отладки с паролем
admin_password = st.text_input("Админский пароль (для отладки)", type="password")
if admin_password == "admin123":
    server_ip = asyncio.run(get_server_ip())
    st.write(f"IP сервера Render: {server_ip}")
    st.write(f"Версия Streamlit: {st.__version__}")
    st.write(f"Версия aiohttp: {aiohttp.__version__}")

# Кнопка расчёта стоимости
if st.button("Рассчитать стоимость"):
    if not address.strip():
        st.error("Введите адрес доставки.")
    else:
        try:
            dest_coords = geocode_address(address, api_key)
            cost, dist_to_exit, nearest_exit, locality, total_distance, method, rate_per_km = await asyncio.run(
                calculate_delivery_cost(cargo_size, dest_coords[0], dest_coords[1], address, routing_api_key, delivery_date)
            )
            st.write(f"Ближайшая точка выхода: {nearest_exit}, расстояние до неё: {dist_to_exit:.2f} км")
            st.write(f"Общее расстояние: {total_distance:.2f} км")
            st.write(f"Стоимость доставки: {cost} руб (тариф: {rate_per_km} руб/км, метод: {method})")
            if locality:
                st.write(f"Населённый пункт: {locality}")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Ошибка расчёта: {str(e)}")

# Синхронизация с Git
if os.getenv("GIT_TOKEN") and os.getenv("GIT_REPO"):
    if st.button("Синхронизировать с Git"):
        try:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", f"Автосохранение {datetime.now()}"], check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], check=True, env={"GIT_TOKEN": os.getenv("GIT_TOKEN")})
            st.success("Синхронизация с Git выполнена успешно.")
        except subprocess.CalledProcessError as e:
            st.error(f"Ошибка синхронизации с Git: {str(e)}")
else:
    st.warning("GIT_TOKEN или GIT_REPO не настроены. Синхронизация с Git недоступна.")
