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

st.set_page_config(page_title="Флора калькулятор (розница)", page_icon="favicon.png")

def is_admin_mode():
    query_params = st.query_params
    return query_params.get("admin", "") == "1"

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

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
            globals()['exit_points'] = []
            globals()['route_groups'] = {}
            return {}
    else:
        st.warning("Файл routes.json не найден. Используются пустые данные.")
        globals()['exit_points'] = []
        globals()['route_groups'] = {}
        return {}
load_routes()

def load_tver_boundary():
    cache_file = 'tver_boundaries.geojson'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Ошибка при загрузке tver_boundaries.geojson: {e}")
            return {}
    return {}

def point_in_polygon(point, polygon):
    x, y = point
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

tver_geojson = load_tver_boundary()
tver_polygon = tver_geojson['features'][0]['geometry']['coordinates'][0] if tver_geojson and tver_geojson.get('features') else []
cargo_prices = {"маленький": 350, "средний": 500, "большой": 800}
distance_table = {}

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
        try:
            if not os.path.exists('.git'):
                subprocess.run(['git', 'init'], check=True, capture_output=True, text=True)
            git_repo = os.environ.get('GIT_REPO', 'https://github.com/floratvertransport-prog/delivery-calc.git')
            git_token = os.environ.get('GIT_TOKEN')
            if git_token:
                git_repo = git_repo.replace('https://', f'https://{git_token}@')
            remote_output = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
            st.session_state.git_remote_status = f"Git remote: {remote_output.stdout.replace(git_token, '******') if git_token else remote_output.stdout or 'No remotes set'}"
            if 'origin' not in remote_output.stdout:
                subprocess.run(['git', 'remote', 'add', 'origin', git_repo], check=True, capture_output=True, text=True)
                st.session_state.git_remote_status = f"Git remote: added origin {git_repo.replace(git_token, '******') if git_token else git_repo}"
            subprocess.run(['git', 'config', '--global', 'user.name', os.environ.get('GIT_USER', 'floratvertransport-prog')], check=True, capture_output=True, text=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'floratvertransport-prog@example.com'], check=True, capture_output=True, text=True)
            branch_output = subprocess.run(['git', 'branch'], capture_output=True, text=True)
            st.session_state.git_branch_status = f"Git branch: {branch_output.stdout}"
            if 'detached' in branch_output.stdout:
                subprocess.run(['git', 'add', cache_file], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'commit', '-m', 'Commit cache.json before checkout'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'checkout', '-B', 'main', 'origin/main'], check=True, capture_output=True, text=True)
                st.session_state.git_branch_status = f"Git branch: switched to main"
            try:
                fetch_result = subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                st.session_state.git_fetch_status = f"Git fetch: {fetch_result.stdout or 'Success'}"
                pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], check=True, capture_output=True, text=True)
                st.session_state.git_pull_status = f"Git pull: {pull_result.stdout or 'Success'}"
            except subprocess.CalledProcessError as e:
                st.session_state.git_sync_status = f"Ошибка git pull: {e}\nSTDERR: {e.stderr}"
                return
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

st.header("Калькулятор стоимости доставки по Твери и области для розничных клиентов")

with st.form("delivery_form"):
    address = st.text_input("Введите адрес доставки")
    cargo_size = st.selectbox("Выберите размер груза", ["маленький", "средний", "большой"])
    delivery_date = st.date_input("Дата доставки", date.today())
    submit_button = st.form_submit_button("Рассчитать")

    if submit_button:
        with st.spinner("Выполняется расчёт..."):
            st.write("Здесь будет логика расчёта доставки (calculate_delivery_cost и т.д.)")

if is_admin_mode():
    st.write("### Админ-режим активирован")
    server_ip = asyncio.run(get_server_ip())
    st.write(f"IP сервера Render: {server_ip}")
    st.write(f"Версия Streamlit: {st.__version__}")
    st.write(f"Версия aiohttp: {aiohttp.__version__}")
    st.write(f"Проверка GIT_TOKEN: {check_git_token()}")

    if 'cache_before_save' in st.session_state:
        with st.expander("Кэш перед сохранением"):
            st.json(st.session_state.cache_before_save)

    if 'cache_after_save' in st.session_state:
        with st.expander("Кэш после сохранения"):
            st.json(st.session_state.cache_after_save)

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
