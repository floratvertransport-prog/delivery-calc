import math
import requests

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

center_lat = 56.8584
center_lon = 35.9006
city_radius = 7.0
rate_per_km = 32
cargo_prices = {
    'small': 350,
    'medium': 500,
    'large': 800
}

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

def calculate_delivery_cost(cargo_size, dest_lat, dest_lon):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза. Доступны: small, medium, large")
    
    base_cost = cargo_prices[cargo_size]
    dist_from_center = haversine(center_lat, center_lon, dest_lat, dest_lon)
    
    if dist_from_center <= city_radius:
        return base_cost
    else:
        dist_from_boundary = dist_from_center - city_radius
        total_extra_distance = dist_from_boundary * 2
        extra_cost = total_extra_distance * rate_per_km
        return round(base_cost + extra_cost, 2)

if __name__ == "__main__":
    api_key = st.secrets["API_KEY"]
    
    print("Добро пожаловать в калькулятор доставки по Твери!")
    cargo_size = input("Введите размер груза (small, medium, large): ").strip().lower()
    address = input("Введите адрес доставки (например, 'Тверь, ул. Советская, 10'): ").strip()
    
    try:
        dest_lat, dest_lon = geocode_address(address, api_key)
        cost = calculate_delivery_cost(cargo_size, dest_lat, dest_lon)
        print(f"Стоимость доставки: {cost} руб.")
    except ValueError as e:

        print(f"Ошибка: {e}")
