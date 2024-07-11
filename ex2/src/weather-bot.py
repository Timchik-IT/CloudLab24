import os
import json
import requests
import io
from datetime import datetime, timezone, timedelta

FUNC_RESPONSE = {
    'statusCode': 200,
    'body': ''
}
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MOSCOW_OFFSET = 3  # Сдвиг времени для московского часового пояса (UTC+3)

def send_message(text, chat_id):
    # Отправка сообщения пользователю Telegram.
    reply_message = {'chat_id': chat_id, 'text': text}
    requests.post(url=f'{TELEGRAM_API_URL}/sendMessage', json=reply_message)

def send_voice(voice, chat_id):
    # Отправка голосового сообщения пользователю Telegram.
    voice_file = {"voice": io.BytesIO(voice)}
    requests.post(url=f'{TELEGRAM_API_URL}/sendVoice', params=chat_id, files=voice_file)


def format_weather_response_voice(weather_data):
    #Форматирование ответа с информацией о погоде для голосового сообщения.
    description = weather_data['weather'][0]['description'].capitalize()
    temp = round(weather_data['main']['temp'])
    feels_like = round(weather_data['main']['feels_like'])
    pressure = round(weather_data['main']['pressure'] * 0.750062)
    humidity = round(weather_data['main']['humidity'])

    response = (f"{description}. "
                f"Температура {temp} градусов цельсия. "
                f"Ощущается как {feels_like} градусов цельсия. "
                f"Давление {pressure} миллиметров ртутного столба. "
                f"Влажность {humidity} процентов.")
    
    return response

def format_weather_response(weather_data):
    # Форматирование ответа с информацией о погоде.
    name = weather_data['name']
    country = weather_data['sys']['country']
    temp = weather_data['main']['temp']
    feels_like = weather_data['main']['feels_like']
    pressure = round(weather_data['main']['pressure'] * 0.750062)  # Преобразование в мм рт. ст.
    humidity = weather_data['main']['humidity']
    visibility = weather_data['visibility']
    wind_speed = weather_data['wind']['speed']
    wind_deg = weather_data['wind']['deg']
    wind_direction = get_wind_direction(wind_deg)
    cloudiness = weather_data['clouds']['all']
    weather_description = weather_data['weather'][0]['description']
    sunrise = convert_utc_to_moscow_time(weather_data['sys']['sunrise'])
    sunset = convert_utc_to_moscow_time(weather_data['sys']['sunset'])
    
    response = (f"{weather_description.capitalize()}.\n"
                f"Температура {temp} ℃, ощущается как {feels_like} ℃.\n"
                f"Атмосферное давление {pressure} мм рт. ст.\n"
                f"Влажность {humidity}%.\n"
                f"Видимость {visibility} метров.\n"
                f"Ветер {wind_speed} м/с, {wind_direction}.\n"
                f"Восход солнца {sunrise} МСК. Закат {sunset} МСК.")
    
    return response

def convert_utc_to_moscow_time(utc_timestamp):
    #Конвертация времени из UTC в московское время.
    utc_time = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    moscow_time = utc_time.astimezone(timezone(timedelta(hours=MOSCOW_OFFSET)))
    return moscow_time.strftime('%H:%M')

def get_wind_direction(deg):
    #Получение направления ветра в текстовом формате.
    directions = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
    ix = round(deg / 45) % 8
    return directions[ix]

def synthesize_voice(text, context, chat_id):
    # Синтез голосового ответа
    tts_url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    headers = {
        "Authorization": f"Bearer {context.token['access_token']}"
    }
    data = {
        "text": text,
        "lang": "ru-RU",
        "voice": "oksana",
        "format": "oggopus"
    }
    response = requests.post(url=tts_url, data=data, headers=headers)
    if not response.ok:
        send_message("Не удалось синтезировать голосовое сообщение", chat_id)
    return response.content


def handle_voice(message_in, context, chat_id):
    file_id = message_in['voice']['file_id']
    file_info = requests.post(url=f'{TELEGRAM_API_URL}/getFile', params={"file_id": file_id}).json()
    
    if not file_info.get('ok'):
        send_message("Не удалось получить файл", chat_id)
        return
    
    file_path = file_info['result']['file_path']
    file_url = f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}'
        
    voice_response = requests.get(file_url).content

    yc_auth = {
        "Authorization": f"Bearer {context.token['access_token']}"
    }
    yc_url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    yc_res = requests.post(url=yc_url, headers=yc_auth, data=voice_response).json()

    if "result" not in yc_res:
        send_message("Не удалось распознать сообщение", chat_id)
        return 
    
    location = yc_res['result']
    
    w_url = "https://api.openweathermap.org/data/2.5/weather"  
    w_params = {
            "q": location,
            "appid": "SecretKey",
            "lang": "ru",
            "units": "metric"
        }
    w_res = requests.get(url=w_url, params=w_params).json()
    if w_res.get('cod') == 200:
        weather_info = format_weather_response(w_res)
        text = format_weather_response_voice(weather_info)
    else:
        if isinstance(location, tuple):
            text = "Я не знаю какая погода в этом месте."
        else:
            text = f'Я не нашел населенный пункт "{location}".'

    voice = synthesize_voice(text, context, chat_id)
    send_voice(voice, chat_id)


def handle_weather_request(location, chat_id):
    #Обработка запроса погоды для указанного местоположения.
    w_url = "https://api.openweathermap.org/data/2.5/weather"
    if isinstance(location, tuple):  # Если location является кортежем с координатами
        lat, lon = location
        w_params = {
            "lat": lat,
            "lon": lon,
            "appid": "SecretKey",
            "lang": "ru",
            "units": "metric"
        }
    else:  # Если location является строкой с названием города
        w_params = {
            "q": location,
            "appid": "SecretKey",
            "lang": "ru",
            "units": "metric"
        }

    try:
        w_res = requests.get(url=w_url, params=w_params).json()
        if w_res.get('cod') == 200:
            weather_info = format_weather_response(w_res)
        else:
            if isinstance(location, tuple):
                weather_info = "Я не знаю какая погода в этом месте."
            else:
                weather_info = f'Я не нашел населенный пункт "{location}".'
    except Exception as e:
        weather_info = "Произошла ошибка при получении данных о погоде."

    send_message(weather_info, chat_id)

def header(event, context):
    if TELEGRAM_BOT_TOKEN is None:
        return FUNC_RESPONSE

    update = json.loads(event['body'])
    if 'message' not in update:
        return FUNC_RESPONSE

    message_in = update['message']
    chat_id = message_in['chat']['id']

    if 'text' in message_in:
        user_text = message_in['text']
        
        if user_text == '/start':
            send_message('Я расскажу о текущей погоде для населенного пункта.', chat_id)
            return FUNC_RESPONSE
        elif user_text == '/help':
            send_message('Я могу ответить на:\n- - Текстовое сообщение с названием населенного пункта.\n- Голосовое сообщение с названием населенного пункта.\n- Сообщение с геопозицией.', chat_id)
            return FUNC_RESPONSE
        else:
            handle_weather_request(user_text, chat_id)
            return FUNC_RESPONSE

    elif 'voice' in message_in:
        voice = message_in['voice']
        if voice['duration'] > 30:
            send_message('Я могу обрабатывать голосовые сообщение не длиннее 30 секунд', chat_id)
            return FUNC_RESPONSE
        
        handle_voice(message_in, context, chat_id) 
        return FUNC_RESPONSE

    elif 'location' in message_in:
        location = message_in['location']
        lat = location['latitude']
        lon = location['longitude']
        handle_weather_request((lat, lon), chat_id)
        return FUNC_RESPONSE

    send_message('Могу обработать только текстовое сообщение с названием населенного пункта или сообщение с геопозицией!', chat_id)
    return FUNC_RESPONSE
