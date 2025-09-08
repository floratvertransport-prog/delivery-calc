import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json
import subprocess
from datetime import date, datetime
from typing import Dict, List, Tuple

# Установка заголовка вкладки
st.set_page_config(page_title="Флора калькулятор (розница)", page_icon="favicon.png")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# Загрузка routes.json
def load_routes():
    cache_file = 'routes.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                globals()['exit_points'] = data.get('exit_points', [])
                globals()['route_groups'] = data.get('route_groups', {})
                return data
        except Exception as e:
            st.warning(f"Ошибка при загрузке routes.json: {e}")
            return {}
    return {}

# Инициализация данных
load_routes()
cargo_prices = {"маленький": 350, "средний": 500, "большой": 800}
distance_table = {}  # Можно расширить, если есть данные

# Словари населённых пунктов с привязкой к конкретным точкам выхода
no_route_localities_point_8 = {
    "деревня Аввакумово": (56.879706, 36.006304),
    "деревня Аркатово": (56.890298, 36.029007),
    "деревня Горютино": (56.891522, 36.058333),
    "деревня Сапково": (56.887168, 36.066890),
    "посёлок Сахарово": (56.897499, 36.049389)
}

no_route_localities_point_7 = {
    "деревня Рябеево": (56.835279, 35.716402),
    "деревня Красново": (56.836976, 35.667727),
    "деревня Мотавино": (56.833959, 35.651731),
    "деревня Прудище": (56.828384, 35.627544),
    "деревня Спичево": (56.823067, 35.612344)
}

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

# Функции для кэша
def load_cache():
    cache_file = 'cache.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Ошибка при загрузке кэша: {e}")
            return {}
    return {}

def save_cache(cache):
    cache_file = 'cache.json'
    try:
        st.session_state.cache_before_save = cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                saved_cache = json.load(f)
                st.session_state.cache_after_save = saved_cache
        # Настройка Git
        try:
            if not os.path.exists('.git'):
                subprocess.run(['git', 'init'], check=True, capture_output=True, text=True)
            git_repo = os.environ.get('GIT_REPO', 'https://github.com/floratvertransport-prog/delivery-calc.git')
            git_token = os.environ.get('GIT_TOKEN')
            if git_token:
                git_repo = git_repo.replace('https://', f'https://{git_token}@')
            # Проверяем и добавляем origin
            remote_output = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
            st.session_state.git_remote_status = f"Git remote: {remote_output.stdout.replace(git_token, '******') if git_token else remote_output.stdout or 'No remotes set'}"
            if 'origin' not in remote_output.stdout:
                subprocess.run(['git', 'remote', 'add', 'origin', git_repo], check=True, capture_output=True, text=True)
                st.session_state.git_remote_status = f"Git remote: added origin {git_repo.replace(git_token, '******') if git_token else git_repo}"
            # Настраиваем Git
            subprocess.run(['git', 'config', '--global', 'user.name', os.environ.get('GIT_USER', 'floratvertransport-prog')], check=True, capture_output=True, text=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'floratvertransport-prog@example.com'], check=True, capture_output=True, text=True)
            # Проверяем текущую ветку и исправляем detached HEAD
            branch_output = subprocess.run(['git', 'branch'], capture_output=True, text=True)
            st.session_state.git_branch_status = f"Git branch: {branch_output.stdout}"
            if 'detached' in branch_output.stdout:
                subprocess.run(['git', 'add', cache_file], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'commit', '-m', 'Commit cache.json before checkout'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'checkout', '-B', 'main', 'origin/main'], check=True, capture_output=True, text=True)
                st.session_state.git_branch_status = f"Git branch: switched to main"
            # Синхронизируем ветку
            try:
                fetch_result = subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                st.session_state.git_fetch_status = f"Git fetch: {fetch_result.stdout or 'Success'}"
                pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], check=True, capture_output=True, text=True)
                st.session_state.git_pull_status = f"Git pull: {pull_result.stdout or 'Success'}"
            except subprocess.CalledProcessError as e:
                st.session_state.git_sync_status = f"Ошибка git pull: {e}\nSTDERR: {e.stderr}"
                return
            # Проверяем изменения
            status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
            st.session_state.git_status = f"Git status: {status_result.stdout}"
            if cache_file in status_result.stdout:
                subprocess.run(['git', 'add', cache_file], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'commit', '-m', 'Update cache.json'], check=True, capture_output=True, text=True)
                try:
                    push_result = subprocess.run(['git', 'push', 'origin', 'main'], check=True, capture_output=True, text=True)
                    st.session_state.git_sync_status = f"Кэш успешно синхронизирован с GitHub: {push_result.stdout or 'Success'}"
                except subprocess.CalledProcessError as e:
                    st.session_state.git_sync_status = f"Ошибка git push: {e}\nSTDERR: {e.stderr}"
            else:
                st.session_state.git_sync_status = "Нет изменений в cache.json для коммита"
        except subprocess.CalledProcessError as e:
            st.session_state.git_sync_status = f"Ошибка синхронизации с GitHub: {e}\nSTDERR: {e.stderr}"
    except Exception as e:
        st.session_state.save_cache_error = f"Ошибка при сохранении кэша: {e}"

# Проверка GIT_TOKEN
def check_git_token():
    git_token = os.environ.get('GIT_TOKEN')
    if not git_token:
        return "Ошибка: GIT_TOKEN не настроен в переменных окружения"
    try:
        response = requests.get('https://api.github.com/user', auth=('floratvertransport-prog', git_token))
        if response.status_code == 200:
            return f"GIT_TOKEN валиден: {response.json().get('login')}"
        else:
            return f"Ошибка проверки GIT_TOKEN: HTTP {response.status_code}, {response.json().get('message', 'Неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка проверки GIT_TOKEN: {str(e)}"

# Геокодирование через Яндекс
@st.cache_data
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

# Получение IP сервера
async def get_server_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipify.org?format=json', timeout=5) as response:
                if response.status == 200:
                    ip_data = await response.json()
                    return ip_data.get('ip', 'Не удалось получить IP')
                else:
                    return f"Ошибка получения IP: HTTP {response.status}"
    except aiohttp.ClientError as e:
        return f"Ошибка соединения при получении IP: {str(e)}"
    except Exception as e:
        return f"Неизвестная ошибка при получении IP: {str(e)}"

# Запрос к ORS
async def get_road_distance_ors(start_lon, start_lat, end_lon, end_lat, api_key):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/geo+json"
    }
    body = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "units": "km",
        "radiuses": [1000, 1000]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    distance = data["routes"][0]["summary"]["distance"]
                    return distance
                else:
                    error_data = await response.json()
                    error_code = error_data.get("error", {}).get("code", 0)
                    error_msg = error_data.get("error", {}).get("message", "Неизвестная ошибка")
                    if error_code == 2010:
                        raise ValueError(f"ORS не нашёл маршрут для координат: {error_msg}. Используется Haversine.")
                    raise ValueError(f"Ошибка ORS API: HTTP {response.status}. Код: {error_code}. Сообщение: {error_msg}")
    except aiohttp.ClientError as e:
        raise ValueError(f"Ошибка соединения с ORS API: {str(e)}")

# Поиск ближайшей точки выхода с точной привязкой по координатам
def find_nearest_exit_point(dest_lat, dest_lon, locality, delivery_date):
    min_dist = float('inf')
    nearest_exit = None
    tolerance = 0.01  # Допуск в градусах (около 1 км)

    # Проверка координат для привязки к точке 8
    for loc, (lat, lon) in no_route_localities_point_8.items():
        if abs(dest_lat - lat) < tolerance and abs(dest_lon - lon) < tolerance:
            nearest_exit = exit_points[7]  # Точка 8 (индекс 7)
            min_dist = haversine(dest_lat, dest_lon, nearest_exit[1], nearest_exit[0])
            return nearest_exit, min_dist

    # Проверка координат для привязки к точке 7
    for loc, (lat, lon) in no_route_localities_point_7.items():
        if abs(dest_lat - lat) < tolerance and abs(dest_lon - lon) < tolerance:
            nearest_exit = exit_points[6]  # Точка 7 (индекс 6)
            min_dist = haversine(dest_lat, dest_lon, nearest_exit[1], nearest_exit[0])
            return nearest_exit, min_dist

    # Если нет точного соответствия, ищем ближайшую точку
    for exit_point in exit_points:
        dist = haversine(dest_lat, dest_lon, exit_point[1], exit_point[0])
        if dist < min_dist:
            min_dist = dist
            nearest_exit = exit_point
    return nearest_exit, min_dist

# Извлечение населённого пункта с точным соответствием
def extract_locality(address):
    known_localities = {**no_route_localities_point_8, **no_route_localities_point_7}
    if 'тверь' in address.lower():
        return 'Тверь'
    if 'завидово' in address.lower() and not 'новозавидовский' in address.lower():
        return 'село Завидово'
    if 'новозавидовский' in address.lower():
        return 'посёлок городского типа Новозавидовский'
    cache = load_cache()
    for locality, (lat, lon) in known_localities.items():
        if locality.lower() in address.lower():
            return locality
    parts = address.split(',')
    for part in parts:
        part = part.strip()
        if part and 'область' not in part.lower() and 'ул.' not in part.lower() and 'г.' not in part.lower():
            return part
    return None

# Проверка соответствия рейсу
def check_route_match(locality, delivery_date):
    if not locality or not delivery_date:
        return False
    # Исключение для населённых пунктов без рейсов
    if locality in no_route_localities_point_8 or locality in no_route_localities_point_7:
        return False
    day_of_week = delivery_date.weekday()
    if str(day_of_week) not in route_groups:
        return False
    for route_name, route_locations in route_groups[str(day_of_week)].items():
        for point in route_locations:
            if locality.lower() in point["name"].lower():
                return True
    return False

# Округление стоимости
def round_cost(cost):
    remainder = cost % 100
    if remainder <= 20:
        return (cost // 100) * 100
    else:
        return ((cost // 100) + 1) * 100

# Расчёт стоимости с учетом рейса
async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key, delivery_date=None, use_route_rate=False):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза. Доступны: маленький, средний, большой")
    base_cost = cargo_prices[cargo_size]
    locality = extract_locality(address)
    st.session_state.locality = locality
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon, locality, delivery_date)
    rate_per_km = 15 if use_route_rate else 32
    if locality and locality.lower() == 'тверь':
        total_distance = 0
        total_cost = base_cost
        return total_cost, dist_to_exit, nearest_exit, locality, total_distance, "город", rate_per_km
    cache = load_cache()
    if locality and locality in cache:
        total_distance = cache[locality]['distance']
        extra_cost = total_distance * rate_per_km
        total_cost = base_cost + extra_cost
        rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
        return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "кэш", rate_per_km
    if routing_api_key and locality:
        try:
            road_distance = await get_road_distance_ors(nearest_exit[0], nearest_exit[1], dest_lon, dest_lat, routing_api_key)
            total_distance = road_distance * 2
            extra_cost = total_distance * rate_per_km
            total_cost = base_cost + extra_cost
            rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
            cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
            save_cache(cache)
            return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "ors", rate_per_km
        except ValueError as e:
            st.warning(f"Ошибка ORS API: {e}. Используется Haversine с коэффициентом 1.3.")
            road_distance = dist_to_exit * 1.3
            total_distance = road_distance * 2
            extra_cost = total_distance * rate_per_km
            total_cost = base_cost + extra_cost
            rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
            if locality:
                cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
                save_cache(cache)
            return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "haversine", rate_per_km
    road_distance = dist_to_exit * 1.3
    total_distance = road_distance * 2
    extra_cost = total_distance * rate_per_km
    total_cost = base_cost + extra_cost
    rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
    if locality:
        cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
        save_cache(cache)
    return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "haversine", rate_per_km

# Streamlit UI
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")
st.write("Введите адрес доставки, выберите размер груза и дату доставки.")
api_key = os.environ.get("API_KEY")
routing_api_key = os.environ.get("ORS_API_KEY")
if not api_key:
    st.error("Ошибка: API-ключ для геокодирования не настроен. Обратитесь к администратору.")
else:
    with st.form(key="delivery_form"):
        cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
        address = st.text_input("Адрес доставки (например, 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино')", value="Тверская область, ")
        delivery_date = st.date_input("Дата доставки", value=date.today(), format="DD.MM.YYYY")
        admin_password = st.text_input("Админ пароль для отладки (оставьте пустым для обычного режима)", type="password")
        submit_button = st.form_submit_button(label="Рассчитать")

        if admin_password == "admin123":
            st.write("Точки выхода из Твери:")
            for i, point in enumerate(exit_points, 1):
                st.write(f"Точка {i}: {point}")
            server_ip = asyncio.run(get_server_ip())
            st.write(f"IP сервера Render: {server_ip}")
            st.write(f"Версия Streamlit: {st.__version__}")
            st.write(f"Версия aiohttp: {aiohttp.__version__}")
            st.write(f"Проверка GIT_TOKEN: {check_git_token()}")
            cache = load_cache()
            st.write(f"Текущий кэш: {cache}")
            if 'cache_before_save' in st.session_state:
                st.write(f"Кэш перед сохранением: {st.session_state.cache_before_save}")
            if 'cache_after_save' in st.session_state:
                st.write(f"Кэш после сохранения: {st.session_state.cache_after_save}")
            if 'save_cache_error' in st.session_state:
                st.write(f"Ошибка сохранения кэша: {st.session_state.save_cache_error}")
            if 'git_sync_status' in st.session_state:
                st.write(f"Статус синхронизации с GitHub: {st.session_state.git_sync_status}")
            if 'git_fetch_status' in st.session_state:
                st.write(f"Статус git fetch: {st.session_state.git_fetch_status}")
            if 'git_pull_status' in st.session_state:
                st.write(f"Статус git pull: {st.session_state.git_pull_status}")
            if 'git_remote_status' in st.session_state:
                st.write(st.session_state.git_remote_status)
            if 'git_branch_status' in st.session_state:
                st.write(st.session_state.git_branch_status)
            if 'git_status' in st.session_state:
                st.write(st.session_state.git_status)
            if not routing_api_key:
                st.warning("ORS_API_KEY не настроен. Для неизвестных адресов используется Haversine с коэффициентом 1.3.")
            else:
                st.success("ORS_API_KEY настроен. Расстояние будет рассчитано по реальным дорогам.")
            if cache:
                st.write("Кэш расстояний:")
                for locality, data in cache.items():
                    st.write(f"{locality}: {data['distance']} км (точка выхода: {data['exit_point']})")

        if submit_button and address:
            try:
                dest_lat, dest_lon = geocode_address(address, api_key)
                locality = extract_locality(address)
                use_route_rate = False
                if check_route_match(locality, delivery_date):
                    st.write("👉 Вы можете доставить этот заказ вместе с оптовыми клиентами")
                    st.write("Доставка по рейсу вместе с оптовыми заказами")
                    use_route = st.checkbox("Использовать доставку по рейсу")
                    if use_route:
                        if not st.session_state.get('route_confirmed', False):
                            confirm = st.radio("Вы точно уверены, что возможна доставка вместе с оптовыми заказами? Время или объём позволяют осуществить доставку вместе с рейсом?", ("Нет", "Да"))
                            if confirm == "Да":
                                st.session_state.route_confirmed = True
                                use_route_rate = True
                            else:
                                st.session_state.route_confirmed = False
                                use_route_rate = False
                        else:
                            use_route_rate = True
                    else:
                        use_route_rate = False
                        if 'route_confirmed' in st.session_state:
                            del st.session_state.route_confirmed
                else:
                    if 'use_route' in st.session_state:
                        del st.session_state.use_route
                    if 'route_confirmed' in st.session_state:
                        del st.session_state.route_confirmed
                result = asyncio.run(calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key, delivery_date, use_route_rate))
                cost, dist_to_exit, nearest_exit, locality, total_distance, source, rate_per_km = result
                st.success(f"Стоимость доставки: {cost} руб.")
                if admin_password == "admin123":
                    st.write(f"Координаты адреса: lat={dest_lat}, lon={dest_lon}")
                    st.write(f"Ближайшая точка выхода: {nearest_exit}")
                    st.write(f"Расстояние до ближайшей точки выхода (по прямой): {dist_to_exit:.2f} км")
                    st.write(f"Извлечённый населённый пункт: {locality}")
                    st.write(f"Источник расстояния: {source}")
                    if source == "город":
                        st.write(f"Населённый пункт: {locality} (доставка в пределах Твери)")
                        st.write(f"Километраж: {total_distance} км (без доплаты)")
                        st.write(f"Базовая стоимость: {cost} руб. (без округления)")
                    elif source in ["таблица", "кэш", "ors", "haversine"]:
                        st.write(f"Населённый пункт: {locality}")
                        st.write(f"Километраж (туда и обратно): {total_distance:.2f} км")
                        st.write(f"Доплата: {total_distance:.2f} × {rate_per_km} = {total_distance * rate_per_km:.2f} руб.")
                    st.write(f"Дата доставки: {delivery_date.strftime('%d.%m.%Y')} ({delivery_date.strftime('%A')})")
                    st.write(f"Использован рейс: {use_route_rate}")
            except ValueError as e:
                st.error(f"Ошибка: {e}")
            except Exception as e:
                st.error(f"Ошибка при расчёте: {e}")
