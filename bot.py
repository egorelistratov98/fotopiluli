import os
import json
import re
import base64
import logging
import requests
import telebot

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
GITHUB_TOKEN   = os.environ['GITHUB_TOKEN']
GITHUB_REPO    = 'egorelistratov98/fotopiluli'
STUDENTS_FILE  = 'students.json'

CHAT_TARIFFS = {
    -1003811884464: 'режиссёрская',
    -1003754896568: 'массовый',
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)


def get_students():
    url     = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{STUDENTS_FILE}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    resp    = requests.get(url, headers=headers)
    data    = resp.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return json.loads(content), data['sha']


def save_students(students, sha):
    url     = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{STUDENTS_FILE}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    encoded = base64.b64encode(
        json.dumps(students, ensure_ascii=False, indent=2).encode('utf-8')
    ).decode('utf-8')
    requests.put(url, headers=headers, json={
        'message': 'Update student progress',
        'content': encoded,
        'sha':     sha,
    })


@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document'])
def handle_message(msg):
    # Ignore messages from bots
    if msg.from_user and msg.from_user.is_bot:
        return

    chat_id = msg.chat.id
    tariff  = CHAT_TARIFFS.get(chat_id)
    if not tariff:
        return

    text = msg.text or msg.caption or ''
    found = re.findall(r'#[Пп]илюля\s*(\d+)', text)
    pills = [int(p) for p in found if 1 <= int(p) <= 9]
    if not pills:
        return

    sender   = msg.from_user
    username = f'@{sender.username}' if sender.username else None
    name     = f'{sender.first_name} {sender.last_name or ""}'.strip()

    try:
        students, sha = get_students()
    except Exception as e:
        logging.error(f'Failed to get students: {e}')
        return

    student = None
    if username:
        student = next(
            (s for s in students if s.get('handle', '').lower() == username.lower()),
            None
        )
    if not student:
        student = next(
            (s for s in students if s.get('name', '').lower() == name.lower()),
            None
        )

    if not student:
        student = {'name': name, 'handle': username or name, 'hw': [], 'tariff': tariff}
        students.append(student)
        logging.info(f'New student: {name} ({tariff})')

    changed = False
    for pill in pills:
        if pill not in student['hw']:
            student['hw'].append(pill)
            student['hw'].sort()
            changed = True

    if changed:
        try:
            save_students(students, sha)
            logging.info(f'Updated {name}: pills {pills}')
        except Exception as e:
            logging.error(f'Failed to save: {e}')


logging.info('Bot starting...')
bot.infinity_polling(timeout=60, long_polling_timeout=60)
