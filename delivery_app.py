import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json
import subprocess
from datetime import date, datetime

try:
    from streamlit_i18n import init, _
    init("ru")
except ImportError:
    def _(text): return text  # Fallback, если streamlit-i18n не установлен

# Установка заголовка вкладки
st.set_page_config(page_title="Флора калькулятор (розница)", page_icon="favicon.png")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# Словарь цен за размер груза
cargo_prices = {
    "маленький": 500,
    "средний": 800,
    "большой": 1200
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

# Точки выхода
exit_points = [
    (36.055364, 56.795587),
    (35.871802, 56.808677),
    (35.804913, 56.831684),
    (36.020937, 56.850973),
    (35.797443, 56.882207),
    (35.932805, 56.902966)
]

# Таблица расстояний с координатами
distance_table = {
    'Клин': {'distance': 140, 'exit_point': (36.055364, 56.795587), 'coords': (36.728611, 56.339167)},
    'Редкино': {'distance': 60, 'exit_point': (36.055364, 56.795587), 'coords': (36.013333, 56.723333)},
    'Мокшино': {'distance': 76, 'exit_point': (36.055364, 56.795587), 'coords': (36.106667, 56.616667)},
    'Новозавидовский': {'distance': 88, 'exit_point': (36.055364, 56.795587), 'coords': (36.050000, 56.533333)},
    'Конаково': {'distance': 134, 'exit_point': (36.055364, 56.795587), 'coords': (36.775000, 56.708333)},
    'Волоколамск': {'distance': 218, 'exit_point': (35.871802, 56.808677), 'coords': (35.957222, 56.035278)},
    'Лотошино': {'distance': 148, 'exit_point': (35.871802, 56.808677), 'coords': (35.506111, 56.047222)},
    'Руза': {'distance': 320, 'exit_point': (35.871802, 56.808677), 'coords': (36.227778, 55.702778)},
    'Шаховская': {'distance': 204, 'exit_point': (35.871802, 56.808677), 'coords': (35.879722, 56.043611)},
    'Великие Луки': {'distance': 740, 'exit_point': (35.804913, 56.831684), 'coords': (30.609167, 56.340278)},
    'Жарковский': {'distance': 640, 'exit_point': (35.804913, 56.831684), 'coords': (32.950833, 55.816667)},
    'Западная Двина': {'distance': 530, 'exit_point': (35.804913, 56.831684), 'coords': (32.055000, 56.250278)},
    'Зубцов': {'distance': 238, 'exit_point': (35.804913, 56.831684), 'coords': (34.583333, 56.183333)},
    'Нелидово': {'distance': 444, 'exit_point': (35.804913, 56.831684), 'coords': (32.775278, 56.225278)},
    'Оленино': {'distance': 350, 'exit_point': (35.804913, 56.831684), 'coords': (33.483333, 56.183333)},
    'Ржев': {'distance': 230, 'exit_point': (35.804913, 56.831684), 'coords': (34.327778, 56.261111)},
    'Старица': {'distance': 132, 'exit_point': (35.804913, 56.831684), 'coords': (34.935000, 56.505278)},
    'Торопец': {'distance': 620, 'exit_point': (35.804913, 56.831684), 'coords': (31.633333, 56.500000)},
    'Дубна': {'distance': 230, 'exit_point': (36.020937, 56.850973), 'coords': (37.166667, 56.733333)},
    'Кимры': {'distance': 186, 'exit_point': (36.020937, 56.850973), 'coords': (37.358333, 56.866667)},
    'Бологое': {'distance': 356, 'exit_point': (35.797443, 56.882207), 'coords': (34.083333, 57.883333)},
    'Вышний Волочек': {'distance': 242, 'exit_point': (35.797443, 56.882207), 'coords': (34.566667, 57.583333)},
    'Лихославль': {'distance': 88, 'exit_point': (35.797443, 56.882207), 'coords': (36.083333, 57.116667)},
    'Спирово': {'distance': 206, 'exit_point': (35.797443, 56.882207), 'coords': (36.416667, 57.416667)},
    'Торжок': {'distance': 122, 'exit_point': (35.797443, 56.882207), 'coords': (34.966667, 57.033333)},
    'Удомля': {'distance': 346, 'exit_point': (35.797443, 56.882207), 'coords': (35.016667, 57.866667)},
    'Сонково': {'distance': 306, 'exit_point': (35.932805, 56.902966), 'coords': (37.150000, 57.783333)},
    'Сандово': {'distance': 474, 'exit_point': (35.932805, 56.902966), 'coords': (36.983333, 58.450000)},
    'Лесное': {'distance': 382, 'exit_point': (35.932805, 56.902966), 'coords': (37.150000, 58.166667)},
    'Максатиха': {'distance': 232, 'exit_point': (35.932805, 56.902966), 'coords': (36.566667, 57.916667)},
    'Рамешки': {'distance': 118, 'exit_point': (35.932805, 56.902966), 'coords': (36.916667, 57.350000)},
    'Весьегонск': {'distance': 486, 'exit_point': (35.932805, 56.902966), 'coords': (37.266667, 58.733333)},
    'Калязин': {'distance': 386, 'exit_point': (35.932805, 56.902966), 'coords': (38.150000, 57.233333)},
    'Кесова Гора': {'distance': 414, 'exit_point': (35.932805, 56.902966), 'coords': (37.616667, 57.883333)},
    'Красный Холм': {'distance': 330, 'exit_point': (35.932805, 56.902966), 'coords': (37.116667, 58.066667)},
    'Бежецк': {'distance': 244, 'exit_point': (35.932805, 56.902966), 'coords': (36.683333, 57.783333)},
    'Кашин': {'distance': 286, 'exit_point': (35.932805, 56.902966), 'coords': (37.616667, 57.300000)},
    'Кувшиново': {'distance': 216, 'exit_point': (35.797443, 56.882207), 'coords': (34.750000, 57.366667)},
    'Осташков': {'distance': 370, 'exit_point': (35.797443, 56.882207), 'coords': (33.116667, 57.150000)},
    'Селижарово': {'distance': 430, 'exit_point': (35.797443, 56.882207), 'coords': (33.466667, 56.850000)},
    'Пено': {'distance': 400, 'exit_point': (35.797443, 56.882207), 'coords': (32.716667, 56.916667)}
}

# Словарь рейсов по дням недели (0 = понедельник, 1 = вторник, и т.д.)
reysy = {
    0: [
        ["Великие Луки", "Жарковский", "Торопец", "Западная Двина", "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"],
        ["Кашин", "Калязин", "Кесова Гора"]
    ],
    1: [
        ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин", "Завидово"],
        ["Руза", "Волоколамск", "Шаховская", "Лотошино"]
    ],
    2: [
        ["Дубна", "Кимры"],
        ["Старица", "Ржев", "Зубцов"],
        ["Кувшиново", "Осташков", "Селижарово", "Пено"]
    ],
    3: [
        ["Великие Луки", "Жарковский", "Торопец", "Западная Двина", "Нелидово", "Оленино"],
        ["Бологое"]
    ],
    4: [
        ["Удомля", "Вышний Волочек", "Спирово", "Торжок", "Лихославль"],
        ["Лесное", "Максатиха", "Рамешки"],
        ["Сандово", "Весьегонск", "Красный Холм", "Сонково", "Бежецк"]
    ]
}

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

# Извлечение населённого пункта и проверка на соответствие рейсу
def extract_locality(address):
    if 'тверь' in address.lower():
        return 'Тверь'
    for locality in distance_table.keys():
        if locality.lower() in address.lower():
            return locality
    if 'завидово' in address.lower():
        return 'Новозавидовский'  # Приведение "Завидово" к "Новозавидовский" для соответствия рейсу
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

def check_route_match(locality, delivery_date):
    if not locality or not delivery_date:
        return None
    day_of_week = delivery_date.weekday()
    if day_of_week not in reysy:
        return None
    for route in reysy[day_of_week]:
        if locality in route:
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
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon)
    locality = extract_locality(address)
    st.session_state.locality = locality
    rate_per_km = 15 if use_route_rate else 32
    if locality and locality.lower() == 'тверь':
        total_distance = 0
        total_cost = base_cost
        return total_cost, dist_to_exit, nearest_exit, locality, total_distance, "город", rate_per_km
    if locality and locality in distance_table:
        total_distance = distance_table[locality]['distance']
        extra_cost = total_distance * rate_per_km
        total_cost = base_cost + extra_cost
        rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
        return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "таблица", rate_per_km
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
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки (например, 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино')", value="Тверская область, ")
    delivery_date = st.date_input("Дата доставки", value=date(2025, 9, 1), format="DD.MM.YYYY")
    admin_password = st.text_input("Админ пароль для отладки (оставьте пустым для обычного режима)", type="password")
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
    if st.button("Рассчитать"):
        if address:
            try:
                dest_lat, dest_lon = geocode_address(address, api_key)
                locality = extract_locality(address)
                use_route_rate = False
                if check_route_match(locality, delivery_date):
                    if 'use_route' not in st.session_state:
                        st.session_state.use_route = False
                    st.write("Доставка по рейсу вместе с оптовыми заказами")
                    if st.checkbox("Использовать доставку по рейсу", value=st.session_state.use_route):
                        if not st.session_state.get('route_confirmed', False):
                            if st.button("Подтвердить использование рейса"):
                                confirm = st.radio("Вы уверены, что данный заказ можно доставить по рейсу вместе с оптовыми заказами?", ("Нет", "Да"))
                                if confirm == "Да":
                                    st.session_state.use_route = True
                                    st.session_state.route_confirmed = True
                                    st.experimental_rerun()
                        else:
                            use_route_rate = True
                    else:
                        st.session_state.route_confirmed = False
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
            except ValueError as e:
                st.error(f"Ошибка: {e}")
            except Exception as e:
                st.error(f"Ошибка при расчёте: {e}")
