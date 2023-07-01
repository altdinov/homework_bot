import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (UserExcHTTPError, UserExcJSONError,
                        UserExcRequestError, UserExcTeleramError)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] func:%(funcName)s '
    'line:%(lineno)d %(message)s'
)
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
            sys.exit(1)


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение "{message}" отправлено успешно')
    except telegram.error.TelegramError as err:
        text = f'Ошибка при отправке сообщения "{message}". Причина:'
        raise UserExcTeleramError(f'{text} {err}')


def get_api_answer(timestamp):
    """Обращение к API Практикум.Домашка."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as err:
        text = 'Ошибка при обращении к API Практикум.Домашка. Причина:'
        raise UserExcRequestError(f'{text} {err}')

    if response.status_code != HTTPStatus.OK:
        text = f'Ошибка HTTP при обращении к API: код {response.status_code}'
        raise UserExcHTTPError(text)

    try:
        response.json()
    except Exception:
        text = 'Ошибка при преобразовании в JSON'
        raise UserExcJSONError(text)

    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие."""
    if not isinstance(response, dict):
        text = f'В ответе API ожидался словарь, получили {type(response)}'
        raise TypeError(text)

    if 'homeworks' not in response:
        text = ('В ответе API в словаре отсутствует ключ "homeworks".'
                f'Ответ содержит следующий словарь: {response}')
        raise KeyError(text)

    if 'current_date' not in response:
        text = ('В ответе API в словаре отсутствует ключ "current_date".'
                f'Ответ содержит следующий словарь: {response}')
        raise KeyError(text)

    homeworks = response['homeworks']
    current_date = response['current_date']

    if not isinstance(homeworks, list):
        text = ('В ответе API значение ключа "homeworks" ожидалось списком,'
                f'получили {type(homeworks)}')
        raise TypeError(text)

    if not isinstance(current_date, int):
        text = ('В ответе API значение ключа "current_date" ожидалось числом,'
                f'получили {type(current_date)}')
        raise TypeError(text)

    return homeworks


def parse_status(homework):
    """Извлечение информации о домашней работе."""
    if not isinstance(homework, dict):
        text = f'Ожидался словарь, получили {type(homework)}'
        raise TypeError(text)

    if 'homework_name' not in homework:
        text = ('В словаре нет ожидаемого ключа "homework_name".'
                f'Ответ содержит следующий словарь: {homework}')
        raise KeyError(text)

    if 'status' not in homework:
        text = ('В "homeworks" нет ожидаемого ключа "status".'
                f'Ответ содержит следующий словарь: {homework}')
        raise KeyError(text)

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        text = '"status" имеет не ожидаемое значение'
        raise ValueError(text)

    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_error_text = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response['current_date']
            if not homeworks:
                logger.debug('Статус домашней работы не изменился')
            else:
                status_text = parse_status(homeworks[0])
                logger.debug(status_text)
                send_message(bot, status_text)
        except UserExcTeleramError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_error_text:
                previous_error_text = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='program.log',
        format=('%(asctime)s [%(levelname)s] func:%(funcName)s '
                'line:%(lineno)d %(message)s'),
    )
    main()
