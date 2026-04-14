import os
import json
import re
import base64
import logging
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat_id = msg.chat_id
    tariff  = CHAT_TARIFFS.get(chat_id)
    if not tariff:
        return

    # Find pill numbers in hashtags: #пилюля1 .. #пилюля9
    found = re.findall(r'#пилюля(\d+)', msg.text, re.IGNORECASE)
    pills = [int(p) for p in found if 1 <= int(p) <= 9]
    if not pills:
        return

    sender   = msg.from_user
    username = f'@{sender.username}' if sender.username else None
    name     = f'{sender.first_name} {sender.last_name or ""}'.strip()

    students, sha = get_students()

    # Find student by username or name
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
        # New student — add automatically
        student = {'name': name, 'handle': username or name, 'hw': [], 'tariff': tariff}
        students.append(student)
        logging.info(f'New student added: {name} ({tariff})')

    changed = False
    for pill in pills:
        if pill not in student['hw']:
            student['hw'].append(pill)
            student['hw'].sort()
            changed = True

    if changed:
        save_students(students, sha)
        logging.info(f'Updated {name}: pills {pills}')


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info('Bot started')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
