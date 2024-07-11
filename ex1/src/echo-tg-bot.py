import os
import json
import requests

FUNC_RESPONSE = {
    'statusCode': 200,
    'body': ''
}
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text, message):

    message_id = message['message_id']
    chat_id = message['chat']['id']
    reply_message = {'chat_id': chat_id,
                     'text': text,
                     'reply_to_message_id': message_id}

    requests.post(url=f'{TELEGRAM_API_URL}/sendMessage', json=reply_message)


def header(event, context):
    if TELEGRAM_BOT_TOKEN is None:
        return FUNC_RESPONSE
    
    update = json.loads(event['body'])

    if 'message' not in update:
        return FUNC_RESPONSE

    message_in = update['message']

    if 'text' not in message_in:
        send_message('Могу обработать только текстовое сообщение!', message_in)
        return FUNC_RESPONSE
    
    echo_text = message_in['text'].upper()
    send_message(echo_text, message_in)

    return FUNC_RESPONSE
