import math
import requests
import streamlit as st
import os

# Функция для расчёта расстояния между двумя точками (Haversine)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Радиус Земли в км
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

# Функция для проверки, внутри ли точка полигона (ray-casting алгоритм)
def is_inside_polygon(point, polygon):
    x, y = point[0], point[1]  # lon, lat
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# Функция для расчёта минимального расстояния до полигона (до ближайшего сегмента)
def distance_to_polygon(point, polygon):
    min_dist = float('inf')
    n = len(polygon)
    for i in range(n):
        a = polygon[i]
        b = polygon[(i + 1) % n]
        dist = distance_to_segment(point, a, b)
        if dist < min_dist:
            min_dist = dist
    return min_dist

# Расстояние от точки до сегмента (a-b)
def distance_to_segment(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    # Векторные расчёты
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    proj = apx * abx + apy * aby
    len_sq = abx * abx + aby * aby
    if len_sq == 0:
        return haversine(py, px, ay, ax)  # a == b
    t = max(0, min(1, proj / len_sq))
    cx = ax + t * abx
    cy = ay + t * aby
    return haversine(py, px, cy, cx)

# Загрузка полигона Твери из OpenStreetMap (relation ID 77760)
def load_tver_polygon():
    url = "http://polygons.openstreetmap.fr/get_geojson.py?id=77760&params=0"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Берём главный полигон (если MultiPolygon, берём первый)
        if data['type'] == 'MultiPolygon':
            polygon = data['coordinates'][0][0]  # Внешний полигон
        elif data['type'] == 'Polygon':
            polygon = data['coordinates'][0]
        else:
            raise ValueError("Неподдерживаемый тип GeoJSON")
        # Меняем [lon, lat] на (lon, lat) для удобства
        polygon = [(lon, lat) for lon, lat in polygon]
        return polygon
    else:
        raise ValueError("Ошибка загрузки полигона Твери")

# Тарифы
rate_per_km = 32
cargo_prices = {
    'маленький': 350,
    'средний': 500,
    'большой': 800
}

# Геокодирование адреса через Яндекс
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={api_key}&geocode={address}&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        try:
            pos = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
            lon, lat = map(float, pos.split(' '))
            return lat, lon
        except (IndexError, KeyError):
            raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь').")
    else:
        raise ValueError(f"Ошибка API: {response.status_code}")

# Расчёт стоимости
def calculate_delivery_cost(cargo_size, dest_lat, dest_lon):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза. Доступны: маленький, средний, большой")
    
    base_cost = cargo_prices[cargo_size]
    
    point = (dest_lon, dest_lat)  # (lon, lat)
    if is_inside_polygon(point, tver_polygon):
        return base_cost
    else:
        dist_from_boundary = distance_to_polygon(point, tver_polygon)
        total_extra_distance = dist_from_boundary * 2
        extra_cost = total_extra_distance * rate_per_km
        return round(base_cost + extra_cost, 2)

# Загрузка полигона один раз при запуске
try:
    tver_polygon = load_tver_polygon()
except ValueError as e:
    st.error(f"Ошибка загрузки границы Твери: {e}")
    tver_polygon = []  # Пустой, чтобы не крашилось

st.title("Калькулятор стоимости доставки по Твери")
st.write("Введите адрес доставки и выберите размер груза.")

api_key = os.environ.get("API_KEY")
if not api_key:
    st.error("Ошибка: API-ключ не настроен. Обратитесь к администратору.")
else:
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки (например, 'Тверь, ул. Советская, 10')")

    if st.button("Рассчитать"):
        if address:
            try:
                dest_lat, dest_lon = geocode_address(address, api_key)
                cost = calculate_delivery_cost(cargo_size, dest_lat, dest_lon)
                st.success(f"Стоимость доставки: {cost} руб.")
            except ValueError as e:
                st.error(f"Ошибка: {e}")
        else:
            st.warning("Введите адрес.")
