import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json

# Функция для расчёта расстояния по прямой (Haversine, для определения направления)
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

# Точки выхода из Твери (координаты административной границы)
exit_points = [
    (36.055364, 56.795587),  # Направление: Клин, Редкино, Мокшино, Новозавидовский, Конаково
    (35.871802, 56.808677),  # Направление: Волоколамск, Лотошино, Руза, Шаховская
    (35.804913, 56.831684),  # Направление: Великие Луки, Жарковский, Западная Двина, Зубцов, Нелидово, Оленино, Ржев, Старица, Торопец
    (36.020937, 56.850973),  # Направление: Дубна, Кимры
    (35.797443, 56.882207),  # Направление: Бологое, Вышний Волочек, Лихославль, Спирово, Торжок, Удомля
    (35.932805, 56.902966)   # Направление: Сонково, Сандово, Лесное, Максатиха, Рамешки, Весьегонск, Калязин, Кесова Гора, Красный Холм, Бежецк, Кашин
]

# Таблица расстояний (туда и обратно, км) как запасной вариант
distance_table = {
    'Клин': {'distance': 140, 'exit_point': (36.055364, 56.795587)},
    'Редкино': {'distance': 60, 'exit_point': (36.055364, 56.795587)},
    'Мокшино': {'distance': 76, 'exit_point': (36.055364, 56.795587)},
    'Новозавидовский': {'distance': 88, 'exit_point': (36.055364, 56.795587)},
    'Конаково': {'distance': 134, 'exit_point': (36.055364, 56.795587)},
    'Волоколамск': {'distance': 218, 'exit_point': (35.871802, 56.808677)},
    'Лотошино': {'distance': 148, 'exit_point': (35.871802, 56.808677)},
    'Руза': {'distance': 320, 'exit_point': (35.871802, 56.808677)},
    'Шаховская': {'distance': 204, 'exit_point': (35.871802, 56.808677)},
    'Великие Луки': {'distance': 740, 'exit_point': (35.804913, 56.831684)},
    'Жарковский': {'distance': 640, 'exit_point': (35.804913, 56.831684)},
    'Западная Двина': {'distance': 530, 'exit_point': (35.804913, 56.831684)},
    'Зубцов': {'distance': 238, 'exit_point': (35.804913, 56.831684)},
    'Нелидово': {'distance': 444, 'exit_point': (35.804913, 56.831684)},
    'Оленино': {'distance': 350, 'exit_point': (35.804913, 56.831684)},
    'Ржев': {'distance': 230, 'exit_point': (35.804913, 56.831684)},
    'Старица': {'distance': 132, 'exit_point': (35.804913, 56.831684)},
    'Торопец': {'distance': 620, 'exit_point': (35.804913, 56.831684)},
    'Дубна': {'distance': 230, 'exit_point': (36.020937, 56.850973)},
    'Кимры': {'distance': 186, 'exit_point': (36.020937, 56.850973)},
    'Бологое': {'distance': 356, 'exit_point': (35.797443, 56.882207)},
    'Вышний Волочек': {'distance': 242, 'exit_point': (35.797443, 56.882207)},
    'Лихославль': {'distance': 88, 'exit_point': (35.797443, 56.882207)},
    'Спирово': {'distance': 206, 'exit_point': (35.797443, 56.882207)},
    'Торжок': {'distance': 122, 'exit_point': (35.797443, 56.882207)},
    'Удомля': {'distance': 346, 'exit_point': (35.797443, 56.882207)},
    'Сонково': {'distance': 306, 'exit_point': (35.932805, 56.902966)},
    'Сандово': {'distance': 474, 'exit_point': (35.932805, 56.902966)},
    'Лесное': {'distance': 382, 'exit_point': (35.932805, 56.902966)},
    'Максатиха': {'distance': 232, 'exit_point': (35.932805, 56.902966)},
    'Рамешки': {'distance': 118, 'exit_point': (35.932805, 56.902966)},
    'Весьегонск': {'distance': 486, 'exit_point': (35.932805, 56.902966)},
    'Калязин': {'distance': 386, 'exit_point': (35.932805, 56.902966)},
    'Кесова Гора': {'distance': 414, 'exit_point': (35.932805, 56.902966)},
    'Красный Холм': {'distance': 330, 'exit_point': (35.932805, 56.902966)},
    'Бежецк': {'distance': 244, 'exit_point': (35.932805, 56.902966)},
    'Кашин': {'distance': 286, 'exit_point': (35.932805, 56.902966)}
}

# Тарифы
rate_per_km = 32
cargo_prices = {
    'маленький': 350,
    'средний': 500,
    'большой': 800
}

# Функции для работы с кэшем
def load_cache():
    cache_file = 'cache.json'
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    try:
        with open('cache.json', 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Ошибка при сохранении кэша: {e}")

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
            raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь' или 'Тверская область').")
    else:
        raise ValueError(f"Ошибка API: {response.status_code}")

# Асинхронный запрос к 2GIS Routing API для дорожного расстояния
async def get_road_distance_2gis(start_lon, start_lat, end_lon, end_lat, api_key):
    url = f"https://catalog-api.2gis.com/3.0/routing/matrix?version=3.0&apikey={api_key}"
    data = {
        "points": [
            {
                "lon": start_lon,
                "lat": start_lat,
                "type": "departure"
            },
            {
                "lon": end_lon,
                "lat": end_lat,
                "type": "arrival"
            }
        ],
        "lang": "ru"
    }
    headers = {'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    distance = data['routes'][0]['distance'] / 1000  # Метры в км
                    return distance
                except (KeyError, IndexError):
                    raise ValueError("Не удалось получить маршрут. Проверьте адрес или API-ключ.")
            else:
                raise ValueError(f"Ошибка 2GIS Routing API: {response.status}")

# Поиск ближайшей точки выхода
def find_nearest_exit_point(dest_lat, dest_lon):
    min_dist = float('inf')
    nearest_exit = None
    for exit_point in exit_points:
        dist = haversine(dest_lat, dest_lon, exit_point[1], exit_point[0])
        if dist < min_dist:
            min_dist = dist
            nearest_exit = exit_point
    return nearest_exit, min_dist

# Извлечение населённого пункта из адреса
def extract_locality(address):
    for locality in distance_table.keys():
        if locality.lower() in address.lower():
            return locality
    cache = load_cache()
    for locality in cache.keys():
        if locality.lower() in address.lower():
            return locality
    parts = address.split(',')
    for part in parts:
        part = part.strip()
        if part and 'область' not in part.lower() and 'ул.' not in part.lower() and 'г.' not in part.lower():
            return part
    return None

# Расчёт стоимости
async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза. Доступны: маленький, средний, большой")
    
    base_cost = cargo_prices[cargo_size]
    
    # Проверяем, внутри ли адрес Твери (если расстояние до ближайшей точки выхода < 5 км)
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon)
    if dist_to_exit < 5:  # Порог для "внутри Твери"
        return base_cost, dist_to_exit, nearest_exit, None, 0, "inside_tver"
    
    # Проверяем таблицу расстояний
    locality = extract_locality(address)
    if locality and locality in distance_table:
        total_distance = distance_table[locality]['distance']
        extra_cost = total_distance * rate_per_km
        return round(base_cost + extra_cost, 2), dist_to_exit, nearest_exit, locality, total_distance, "table"
    
    # Проверяем кэш
    cache = load_cache()
    if locality and locality in cache:
        total_distance = cache[locality]['distance']
        extra_cost = total_distance * rate_per_km
        return round(base_cost + extra_cost, 2), dist_to_exit, nearest_exit, locality, total_distance, "cache"
    
    # Используем 2GIS Routing API для дорожного расстояния
    if routing_api_key and locality:
        try:
            road_distance = await get_road_distance_2gis(nearest_exit[0], nearest_exit[1], dest_lon, dest_lat, routing_api_key)
            total_distance = road_distance * 2  # Туда и обратно
            extra_cost = total_distance * rate_per_km
            # Сохраняем в кэш
            cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
            save_cache(cache)
            return round(base_cost + extra_cost, 2), dist_to_exit, nearest_exit, locality, total_distance, "2gis"
        except ValueError as e:
            st.warning(f"Ошибка 2GIS Routing API: {e}. Используется Haversine с коэффициентом 1.5.")
            # Падение на Haversine с коэффициентом
            road_distance = dist_to_exit * 1.5
            total_distance = road_distance * 2
            extra_cost = total_distance * rate_per_km
            if locality:
                cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
                save_cache(cache)
            return round(base_cost + extra_cost, 2), dist_to_exit, nearest_exit, locality, total_distance, "haversine"
    else:
        # Если ключ не настроен, используем Haversine с коэффициентом 1.5
        road_distance = dist_to_exit * 1.5
        total_distance = road_distance * 2
        extra_cost = total_distance * rate_per_km
        if locality:
            cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
            save_cache(cache)
        return round(base_cost + extra_cost, 2), dist_to_exit, nearest_exit, locality, total_distance, "haversine"

# Streamlit UI
st.title("Калькулятор стоимости доставки по Твери")
st.write("Введите адрес доставки и выберите размер груза.")

api_key = os.environ.get("API_KEY")
routing_api_key = os.environ.get("GIS_ROUTING_API_KEY")
if not api_key:
    st.error("Ошибка: API-ключ для геокодирования не настроен. Обратитесь к администратору.")
else:
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки (например, 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино')")
    admin_password = st.text_input("Админ пароль для отладки (оставьте пустым для обычного режима)", type="password")

    if admin_password == "admin123":  # Измените пароль на свой
        st.write("Точки выхода из Твери:")
        for i, point in enumerate(exit_points, 1):
            st.write(f"Точка {i}: {point}")
        if not routing_api_key:
            st.warning("GIS_ROUTING_API_KEY не настроен. Для неизвестных адресов используется Haversine с коэффициентом 1.5.")
        else:
            st.success("GIS_ROUTING_API_KEY настроен. Расстояние будет рассчитано по реальным дорогам.")
        cache = load_cache()
        if cache:
            st.write("Кэш расстояний:")
            for locality, data in cache.items():
                st.write(f"{locality}: {data['distance']} км (точка выхода: {data['exit_point']})")

    if st.button("Рассчитать"):
        if address:
            try:
                dest_lat, dest_lon = geocode_address(address, api_key)
                # Оборачиваем асинхронный вызов в asyncio.run()
                result = asyncio.run(calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key))
                cost, dist_to_exit, nearest_exit, locality, total_distance, source = result
                st.success(f"Стоимость доставки: {cost} руб.")
                if admin_password == "admin123":
                    st.write(f"Координаты адреса: lat={dest_lat}, lon={dest_lon}")
                    st.write(f"Ближайшая точка выхода: {nearest_exit}")
                    st.write(f"Расстояние до ближайшей точки выхода (по прямой): {dist_to_exit:.2f} км")
                    st.write(f"Адрес внутри Твери: {dist_to_exit < 5}")
                    st.write(f"Источник расстояния: {source}")
                    if source == "table":
                        st.write(f"Населённый пункт из таблицы: {locality}")
                        st.write(f"Километраж из таблицы (туда и обратно): {total_distance} км")
                        st.write(f"Доплата: {total_distance} × 32 = {total_distance * 32} руб.")
                    elif source == "cache":
                        st.write(f"Населённый пункт из кэша: {locality}")
                        st.write(f"Километраж из кэша (туда и обратно): {total_distance} км")
                        st.write(f"Доплата: {total_distance} × 32 = {total_distance * 32} руб.")
                    elif source == "2gis":
                        st.write(f"Населённый пункт: {locality}")
                        st.write(f"Километраж по реальным дорогам (туда и обратно): {total_distance:.2f} км")
                        st.write(f"Доплата: {total_distance:.2f} × 32 = {total_distance * 32:.2f} руб.")
                    elif source == "haversine":
                        st.write(f"Населённый пункт: {locality}")
                        st.write(f"Километраж по Haversine с коэффициентом 1.5 (туда и обратно): {total_distance:.2f} км")
                        st.write(f"Доплата: {total_distance:.2f} × 32 = {total_distance * 32:.2f} руб.")
                    else:
                        st.write("Доставка внутри Твери, доплата не начислена.")
            except ValueError as e:
                st.error(f"Ошибка: {e}")
            except Exception as e:
                st.error(f"Ошибка при расчёте: {e}")
        else:
            st.warning("Введите адрес.")

