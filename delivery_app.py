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
from urllib.parse import urlparse, parse_qs

# Установка заголовка вкладки
st.set_page_config(page_title="Флора калькулятор (розница)", page_icon="favicon.png")

# Получение параметра admin из URL
def is_admin_mode():
    query_params = st.query_params
    return query_params.get("admin", "") == "1"

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

# Загрузка границ Твери из Geo
