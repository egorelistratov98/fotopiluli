import os
import json
import re
import base64
import logging
import requests
from flask import Flask, request

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN      = os.environ['TELEGRAM_TOKEN']
GITHUB_TOKEN        = os.environ['GITHUB_TOKEN']
SALEBOT_WEBHOOK_URL = os.environ['SALEBOT_WEBHOOK_URL']
GITHUB_REPO         = 'egorelistratov98/fotopiluli'
STUDENTS_FILE       = 'students.json'

CHAT_TARIFFS = {
    -1003811884464: 'режиссёрская',
    -1003754896568: 'массовый',
}

app = Flask(__name__)


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


def handle_message(msg):
    from_user = msg.get('from', {})
    if from_user.get('is_bot'):
        return

    chat_id = msg.get('chat', {}).get('id')
    tariff  = CHAT_TARIFFS.get(chat_id)
    if not tariff:
        return

    text = msg.get('text') or msg.get('caption') or ''
    found = re.findall(r'#[Пп]илюля\s*(\d+)', text)
    pills = [int(p) for p in found if 1 <= int(p) <= 9]
    if not pills:
        return

    username = f'@{from_user["username"]}' if from_user.get('username') else None
    first    = from_user.get('first_name', '')
    last     = from_user.get('last_name', '')
    name     = f'{first} {last}'.strip()

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


@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()

    # Forward everything to SaleBot (activations, private messages, etc.)
    try:
        requests.post(SALEBOT_WEBHOOK_URL, json=update, timeout=3)
    except Exception as e:
        logging.warning(f'SaleBot forward failed: {e}')

    # Process homework hashtags from group messages
    if update and 'message' in update:
        try:
            handle_message(update['message'])
        except Exception as e:
            logging.error(f'handle_message error: {e}')

    return 'OK', 200


@app.route('/', methods=['GET'])
def index():
    return 'Bot is running', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logging.info('Bot starting (webhook mode)...')
    app.run(host='0.0.0.0', port=port)
