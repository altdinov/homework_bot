import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s [%(levelname)s] %(message)s',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SECOND_IN_MONTH = 2592000

privious_status = None
previous_message = None


def check_tokens():
    """Проверка доступности переменных окружения."""
    env_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in env_variables.items():
        if value is None:
            text = f'Переменная окружения {key} отсутствует'
            logger.critical(f'{text}. Работа программы завершена')
            raise ValueError(text)


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    global previous_message
    try:
        if previous_message != message:
            previous_message = message
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logger.debug(f'Сообщение "{message}" отправлено успешно')
    except Exception as err:
        text = 'Ошибка при отправке сообщения в Telegram'
        logger.error(f'{text}\n{err}', exc_info=True)


def get_api_answer(timestamp):
    """Обращение к API Практикум.Домашка."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as err:
        text = 'Ошибка при обращении к API Практикум.Домашка'
        send_message(bot, text)
        logger.error(f'{text}\n{err}', exc_info=True)
        raise ValueError(text)
    if response.status_code != HTTPStatus.OK:
        text = f'Ошибка HTTP при обращении к API: код {response.status_code}'
        send_message(bot, text)
        logger.error(f'{text}')
        raise requests.exceptions.HTTPError(text)
    try:
        response.json()
    except Exception as err:
        text = 'Ошибка при преобразовании в JSON'
        send_message(bot, text)
        logger.error(f'{text}\n{err}', exc_info=True)
        raise requests.exceptions.JSONDecodeError(text)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not isinstance(response, dict):
        text = 'При преобразовании ответа от API ожидался словарь'
        send_message(bot, text)
        logger.error(f'{text}')
        raise TypeError(text)
    homeworks = response.get('homeworks')
    current_date = response.get('current_date')
    if homeworks is None:
        text = 'В ответе API нет ожидаемого ключа "homeworks"'
        send_message(bot, text)
        logger.error(f'{text}')
        raise KeyError(text)
    if not isinstance(homeworks, list):
        text = 'В ответе API значение ключа "homeworks" ожидалось списком'
        send_message(bot, text)
        logger.error(f'{text}')
        raise TypeError(text)
    if not isinstance(current_date, int):
        text = 'В ответе API значение ключа "current_date" ожидалось числом'
        send_message(bot, text)
        logger.error(f'{text}')
        raise TypeError(text)
    if current_date is None:
        text = 'В ответе API нет ожидаемого ключа "current_date"'
        send_message(bot, text)
        logger.error(f'{text}')
        raise KeyError(text)
    if len(homeworks) == 0:
        text = 'В ответе API нет данных в "homeworks"'
        send_message(bot, text)
        logger.error(f'{text}')
        raise ValueError(text)
    # Возвращаем только последнюю домашнюю работу
    return homeworks[0]


def parse_status(homework):
    """Извлечение информации о домашней работе."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None:
        text = 'В домашней работе нет ожидаемого ключа "homework_name"'
        send_message(bot, text)
        logger.error(f'{text}')
        raise KeyError(text)
    if status is None:
        text = 'В домашней работе нет ожидаемого ключа "status"'
        send_message(bot, text)
        logger.error(f'{text}')
        raise KeyError(text)
    if status not in HOMEWORK_VERDICTS:
        text = '"status" имеет не ожидаемое значение'
        send_message(bot, text)
        logger.error(f'{text}')
        raise ValueError(text)
    global privious_status
    if status != privious_status:
        privious_status = status
        verdict = HOMEWORK_VERDICTS.get(status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logger.debug('Статус домашней работы не изменен')
        return None


def main():
    """Основная логика работы бота."""
    check_tokens()
    while True:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        previous_time = timestamp - SECOND_IN_MONTH
        try:
            response = get_api_answer(previous_time)
            homework = check_response(response)
            status = parse_status(homework)
            send_message(bot, status)
        except Exception as error:
            print(error)
            message = f'Сбой в работе программы: {error}'
            logger.critical(f'{message}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
