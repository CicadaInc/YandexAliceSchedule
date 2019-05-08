from flask import Flask, request
import logging
import json
import requests
from datetime import datetime
import re

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# User-data (key = user_id)
sessionStorage = {}


@app.route("/post", methods=['POST'])
def main():
    # The main function

    # Form the base structure of response
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }

    # Launch the dialog handler
    handle_dialog(response, request.json)

    return json.dumps(response)


def handle_dialog(res, req):
    try:
        user_id = req['session']['user_id']

        if req['session']['new']:

            # Empty storage of user
            sessionStorage[user_id] = {}

            # User din't wrote any info yet
            sessionStorage[user_id]['geo_response'] = None
            sessionStorage[user_id]['true_address'] = False
            sessionStorage[user_id]['true_station'] = False
            sessionStorage[user_id]['transport_type'] = False
            sessionStorage[user_id]['test'] = True
            sessionStorage[user_id]['station_type_search'] = False
            sessionStorage[user_id]['nearest_stations_buttons'] = False
            sessionStorage[user_id]['date'] = False
            sessionStorage[user_id]['link_to_trips'] = False
            sessionStorage[user_id]['day'] = 'schedule'
            sessionStorage[user_id]['key_word'] = False
            sessionStorage[user_id]['other_key'] = False
            sessionStorage[user_id]['search'] = False
            sessionStorage[user_id]['try'] = 0

            sessionStorage[user_id]['date_buttons'] = [
                {
                    'title': 'Сегодня',
                    'hide': True
                },
                {
                    'title': 'Завтра',
                    'hide': True
                }
            ]

            res['response'][
                'text'] = 'Привет! Я могу рассказать о нужной Вам станции (будь то автобусной, авиастанции и тому подобных)! ' \
                          'Скажите, где Вы находитесь или адрес, от которого будет происходить поиск станций.'

            set_help_buttons(user_id, res)

        else:
            # Block to show the races schedule of once station

            tokens = req['request']['nlu']['tokens']
            entities = req['request']['nlu']['entities']

            if sessionStorage[user_id]['key_word']:
                receive_stations_by_key(user_id, res, tokens)

            elif 'помощь' in tokens or {'что', 'ты', 'умеешь'}.issubset(tokens):
                res['response'][
                    'text'] = 'Я могу рассказать Вам информарцию о рейсах на тот или иной день. Следуйте моим указаниям.'

            elif {'изменить', 'адрес'}.issubset(tokens) or {'другой', 'адрес'}.issubset(tokens):
                # User want to edit the address (come back to begin of address select)
                sessionStorage[user_id]['transport_type'] = False
                sessionStorage[user_id]['true_address'] = False
                sessionStorage[user_id]['true_station'] = False
                sessionStorage[user_id]['geo_response'] = None
                sessionStorage[user_id]['link_to_trips'] = False
                sessionStorage[user_id]['station_type_search'] = False
                sessionStorage[user_id]['nearest_stations_buttons'] = False
                sessionStorage[user_id]['other_key'] = False
                sessionStorage[user_id]['test'] = True
                sessionStorage[user_id]['date'] = False
                sessionStorage[user_id]['search'] = False
                sessionStorage[user_id]['try'] = 0

                res['response']['text'] = 'Скажите адрес, от которого будет происходить поиск станций'

            elif {'изменить', 'тип', 'транспорта'}.issubset(tokens) or {'изменить', 'транспорт'}.issubset(tokens):
                # That data needs to clean to start searching again
                sessionStorage[user_id]['transport_type'] = True
                sessionStorage[user_id]['link_to_trips'] = False
                sessionStorage[user_id]['true_station'] = False
                sessionStorage[user_id]['other_key'] = False
                sessionStorage[user_id]['date'] = False
                sessionStorage[user_id]['nearest_stations_buttons'] = False
                sessionStorage[user_id]['search'] = False
                sessionStorage[user_id]['station_type_search'] = False

                res['response']['text'] = 'Выберите тип транспорта.'

            elif {'изменить', 'тип', 'поиска'}.issubset(tokens):
                handle_search(res, tokens, user_id)
                sessionStorage[user_id]['search'] = False
                sessionStorage[user_id]['other_key'] = False
                sessionStorage[user_id]['true_station'] = False
                sessionStorage[user_id]['nearest_stations_buttons'] = False

            elif {'изменить', 'станцию'}.issubset(tokens) or {'другую', 'станцию'}.issubset(tokens):
                sessionStorage[user_id]['true_station'] = False
                sessionStorage[user_id]['date'] = False
                sessionStorage[user_id]['nearest_stations_buttons'] = False
                sessionStorage[user_id]['other_key'] = False

                receive_stations(user_id, res)

            elif {'другое', 'слово'}.issubset(tokens):
                sessionStorage[user_id]['key_word'] = True
                res['response']['text'] = 'Слушаю'
                sessionStorage[user_id]['other_key'] = False

            elif {'самолёт', 'поезд', 'электричка', 'автобус', 'морской', 'вертолёт'}.intersection(tokens):
                handle_search(res, tokens, user_id)

            elif 'молодец' in tokens:
                res['response']['text'] = 'Как мило. Спасибо!'

            elif 'отлично' in tokens:
                res['response']['text'] = 'Я очень рада, что Вам нравится!'

            elif 'сегодня' in tokens:
                sessionStorage[user_id]['date'] = str(datetime.today())[:10]
                sessionStorage[user_id]['day'] = 'today'
                receive_schedule(res, user_id)

            elif 'завтра' in tokens:
                sessionStorage[user_id]['date'] = str(datetime.today())[:10]
                sessionStorage[user_id]['day'] = 'tomorrow'
                receive_schedule(res, user_id)

            elif 'ближайшие' in tokens and 'ключевому' not in tokens:
                receive_stations(user_id, res)

                sessionStorage[user_id]['search'] = True
                sessionStorage[user_id]['station_type_search'] = False

            elif 'ближайшие' not in tokens and 'ключевому' in tokens:
                sessionStorage[user_id]['station_type_search'] = False
                sessionStorage[user_id]['other_key'] = False

                res['response']['text'] = 'Назовите ключевое слово'

                sessionStorage[user_id]['search'] = True
                sessionStorage[user_id]['key_word'] = True

            elif not sessionStorage[user_id]['true_address']:
                # User didn't wrote a name of station yet
                sessionStorage[user_id]['true_station'] = False

                handle_address(res, tokens, user_id)

            elif not sessionStorage[user_id]['true_station']:
                handle_station(res, tokens, user_id)

            elif {'посмотреть', 'рейсы'}.issubset(tokens):
                res['response'][
                    'text'] = 'Открываю рейсы. Также Вы можете сейчас ввести другую дату или изменить параметры. Используйте кнопки для удобства.'

            elif {'открыть', 'карты'}.issubset(tokens):
                res['response'][
                    'text'] = 'Открываю карты. Также Вы можете сейчас ввести другую дату или изменить параметры. Используйте кнопки для удобства.'

            else:
                # Receiving the schedule of the specified station, date and time

                if handle_datetime(res, user_id, entities):
                    receive_schedule(res, user_id)
                else:
                    res['response']['text'] = 'Я не понимаю. Попробуйте сказать по-другому или измените команду.'

            if not res['response']['end_session']:
                set_help_buttons(user_id, res)
    except Exception as error:
        print(str(error))
        res['response']['text'] = 'Я Вас немного не понимаю, попробуйте сказать по-другому пожалуйста.'


def receive_schedule(res, user_id):
    # Form schedule response
    schedule_params = {
        "apikey": "0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a",
        "station": sessionStorage[user_id]['station']['code'],
        "date": sessionStorage[user_id]['date'],
        "transport_types": sessionStorage[user_id]['transport_type_req']
    }
    sessionStorage[user_id]['schedule_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/schedule/",
        params=schedule_params).json()

    link = 'https://rasp.yandex.ru/station/' + sessionStorage[user_id]['station']['code'][1:] + '/?start=' + \
           sessionStorage[user_id]['date'].replace('.', '-') + '&span=' + sessionStorage[user_id]['day']

    sessionStorage[user_id]['link_to_trips'] = link

    res['response']['text'] = 'Переходите по ссылке в кнопке.'


def handle_search(res, tokens, user_id):
    sessionStorage[user_id]['link_to_trips'] = False
    types = {
        'самолёт': 'plane',
        'поезд': 'train',
        'электричка': 'suburban',
        'автобус': 'bus',
        'морской': 'water',
        'вертолёт': 'helicopter'
    }

    sessionStorage[user_id]['transport_type'] = True

    if not sessionStorage[user_id]['search']:
        sessionStorage[user_id]['transport_type_req'] = types[str(list(
            {'самолёт', 'поезд', 'электричка', 'автобус', 'морской', 'вертолёт'}.intersection(tokens))[0])]

    sessionStorage[user_id]['station_type_search'] = True
    res['response']['text'] = 'Отлично! Найти ближайшие станции или по ключевому слову?'

    sessionStorage[user_id]['transport_type'] = False


# Date normalization to ISO 8601
def date_normalization(day, month, year):
    # String date formatting

    if len(month) == 1:
        month = '0' + month
    if len(day) == 1:
        day = '0' + day

    return year + '-' + month + '-' + day


def handle_datetime(res, user_id, entities):
    # This function to format and handle date and time (write them in storage)
    for entity in entities:
        if entity['type'] == 'YANDEX.DATETIME':
            sessionStorage[user_id]['date'] = '{}.{}.{}'.format(entity['value']['year'], entity['value']['month'],
                                                                entity['value']['day'])

            # res['response']['text'] = '{}.{}.{}'.format(entity['value']['day'], entity['value']['month'],
            #                                             entity['value']['year'])

            sessionStorage[user_id]['true_date'] = True
            return True
    return False


def handle_station(res, tokens, user_id):
    # Function to handles the sent station

    sessionStorage[user_id]['nearest_stations_buttons'] = False

    # Requested name
    station_name = ' '.join(tokens)

    logging.info(station_name)

    for station in sessionStorage[user_id]['stations_response']['stations'][:3]:
        # Name from json-request
        station_name1 = '{} {}'.format(station['station_type_name'], station['title']).lower().replace('-', ' ')
        station_name1 = ''.join([el for el in station_name1 if el == ' ' or el.isalnum()])
        logging.info(station_name1)

        if station_name1 == station_name:
            res['response']['text'] = 'Вы выбрали станцию "{}".\n' \
                                      'Теперь назовите нужную дату.'.format(station_name1)

            sessionStorage[user_id]['true_station'] = True
            sessionStorage[user_id]['station'] = station

            return

    # We didn't find requested station
    res['response']['text'] = 'Результатов на данный запрос не найдено.'


def handle_address(res, tokens, user_id):
    # Function handles the request when user has written an address

    if not sessionStorage[user_id]['geo_response']:
        # First try

        try:
            address = ' '.join(tokens)

            # Form geocoder request to get coordinates of designated address
            geo_params = {
                'geocode': address,
                'format': 'json'
            }
            sessionStorage[user_id]['geo_response'] = requests.get("https://geocode-maps.yandex.ru/1.x/",
                                                                   params=geo_params).json()["response"]

            # Find toponym with index = try
            user_try = sessionStorage[user_id]['try']
            toponym = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][user_try]

            res['response']['text'] = 'Вы имеете ввиду этот адрес: {}?'.format(
                toponym['GeoObject']['metaDataProperty']['GeocoderMetaData']['text'])

            sessionStorage[user_id]['test'] = False

        except IndexError:
            sessionStorage[user_id]['geo_response'] = None
            res['response']['text'] = 'Не поняла адреса'

    elif 'да' in tokens and 'нет' not in tokens:
        # If user confirmed address

        sessionStorage[user_id]['transport_type'] = True

        res['response']['text'] = 'Выберите тип транспорта.'

        sessionStorage[user_id]['true_address'] = True

        # receive_stations(user_id, res)

    elif 'нет' in tokens and 'да' not in tokens:
        #  Handle the try to write address

        try:
            # We try to get another because user didn't confirmed an address
            sessionStorage[user_id]['try'] += 1

            # Find toponym with index = try
            toponym = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
                sessionStorage[user_id]['try']]

            res['response']['text'] = 'Вы имеете ввиду этот адрес: {}?'.format(
                toponym['GeoObject']['metaDataProperty']['GeocoderMetaData']['text'])

            sessionStorage[user_id]['test'] = False

            # If user does not confirm the address we will try to get another
            sessionStorage[user_id]['try'] += 1
            if sessionStorage[user_id]['try'] == 5:  # Too many tries
                raise IndexError

        except IndexError:
            # We can't find anymore geo objects
            res['response']['text'] = 'Уточните адрес, пожалуйста'
            sessionStorage[user_id]["geo_response"] = None
            sessionStorage[user_id]['try'] = 0

    else:
        res['response']['text'] = 'Не поняла ответа. Да или нет?'


def receive_stations_by_key(user_id, res, tokens):
    sessionStorage[user_id]['true_address'] = True  # Valid address

    sessionStorage[user_id]['key_word'] = False

    user_try = sessionStorage[user_id]['try']
    lng, lat = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
        user_try]["GeoObject"]["Point"]["pos"].split()

    #  Find the five nearest stations
    schedule_params = {
        'apikey': '0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a',
        'transport_types': sessionStorage[user_id]['transport_type_req'],
        'distance': 50,  # we are looking for stations only in our city
        'lat': lat,
        'lng': lng
    }
    sessionStorage[user_id]['stations_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/nearest_stations/",
        params=schedule_params).json()
    stations = sessionStorage[user_id]['stations_response']['stations'][:3]

    sessionStorage[user_id]['nearest_stations_buttons'] = []

    text_response = 'Первые найденые совпадения: \n\n'
    for station in stations:

        tokens = normalization(tokens)
        station_tok = normalization(str(station['station_type_name'] + ' ' + station['title']).split())

        print(tokens)
        print(station_tok)
        print(set(tokens).issubset(set(station_tok)))

        if set(tokens).issubset(set(station_tok)):
            distance = round(station['distance'], 3)
            text_response += '{} {}\n' \
                             'Расстояние: {} км\n\n'.format(station['station_type_name'], station['title'], distance)
            sessionStorage[user_id]['nearest_stations_buttons'] += [
                {
                    'title': station['station_type_name'] + ' ' + station['title'],
                    'hide': True
                }
            ]

    if len(sessionStorage[user_id]['nearest_stations_buttons']) != 0:
        text_response += 'Скажите полное имя станции, чтобы узнать расписание ее рейсов.'

        res['response']['text'] = text_response
    else:
        res['response']['text'] = 'Таких станций не найдено.'
        sessionStorage[user_id]['other_key'] = True


def receive_stations(user_id, res):
    sessionStorage[user_id]['true_address'] = True  # Valid address

    user_try = sessionStorage[user_id]['try']
    lng, lat = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
        user_try]["GeoObject"]["Point"]["pos"].split()

    #  Find the five nearest stations
    schedule_params = {
        'apikey': '0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a',
        'transport_types': sessionStorage[user_id]['transport_type_req'],
        'distance': 50,  # this is done to know the nearest stations at a great distance
        'lat': lat,
        'lng': lng
    }
    sessionStorage[user_id]['stations_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/nearest_stations/",
        params=schedule_params).json()
    try:
        stations = sessionStorage[user_id]['stations_response']['stations'][:3]
    except Exception:
        res['response']['text'] = 'Таких станций не найдено.'
        return

    sessionStorage[user_id]['nearest_stations_buttons'] = []

    text_response = 'Ближайшие станции: \n\n'
    for station in stations:
        distance = round(station['distance'], 3)
        text_response += '{} {}\n' \
                         'Расстояние: {} км\n\n'.format(station['station_type_name'], station['title'], distance)
        sessionStorage[user_id]['nearest_stations_buttons'] += [
            {
                'title': station['station_type_name'] + ' ' + station['title'],
                'hide': True
            }
        ]

    if len(sessionStorage[user_id]['nearest_stations_buttons']) != 0:
        text_response += 'Скажите полное имя станции, чтобы узнать расписание ее рейсов'

        sessionStorage[user_id]['other_key'] = False
        res['response']['text'] = text_response
    else:
        res['response']['text'] = 'Таких станций не найдено.'


def set_help_buttons(user_id, res):
    # This function add in response help-buttons according to user status

    res['response']['buttons'] = []

    if sessionStorage[user_id]['other_key']:
        res['response']['buttons'] += [
            {
                'title': 'Другое слово',
                'hide': True
            }
        ]

    if sessionStorage[user_id]['true_station'] and sessionStorage[user_id]['link_to_trips'] is False:
        res['response']['buttons'] += sessionStorage[user_id]['date_buttons']

    if sessionStorage[user_id]['link_to_trips'] is not False:
        res['response']['buttons'] += [
            {
                'title': 'Посмотреть рейсы',
                'url': sessionStorage[user_id]['link_to_trips'],
                'hide': True
            }
        ]

        res['response']['buttons'] += [
            {
                'title': 'Открыть карты',
                'url': 'https://yandex.ru/maps/',
                'hide': True
            }
        ]

    if type(sessionStorage[user_id]['nearest_stations_buttons']) == list:
        res['response']['buttons'] += sessionStorage[user_id]['nearest_stations_buttons']

    if sessionStorage[user_id]['station_type_search']:
        res['response']['buttons'] += [
            {
                'title': 'Ближайшие',
                'hide': True
            },
            {
                'title': 'По ключевому слову',
                'hide': True
            }
        ]

    if sessionStorage[user_id]['transport_type']:
        res['response']['buttons'] += [
            {
                'title': 'Самолёт',
                'hide': True
            },
            {
                'title': 'Поезд',
                'hide': True
            },
            {
                'title': 'Электричка',
                'hide': True
            },
            {
                'title': 'Автобус',
                'hide': True
            },
            {
                'title': 'Морской транспорт',
                'hide': True
            },
            {
                'title': 'Вертолёт',
                'hide': True
            }
        ]

    if sessionStorage[user_id]['test']:
        res['response']['buttons'] += [
            {
                'title': 'Москва, ул. Льва Толстого, 16',
                'hide': True
            }
        ]

    if sessionStorage[user_id]['search']:
        res['response']['buttons'] += [
            {
                'title': 'Изменить тип поиска',
                'hide': True
            }
        ]

    if sessionStorage[user_id]['geo_response']:
        if not sessionStorage[user_id]['true_address']:
            res['response']['buttons'] += [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                },
            ]
        res['response']['buttons'] += [
            {
                'title': 'Изменить адрес',
                'hide': True
            }
        ]
        if not sessionStorage[user_id]['transport_type'] and sessionStorage[user_id]['true_address']:
            res['response']['buttons'] += [
                {
                    'title': 'Изменить тип транспорта',
                    'hide': True
                }
            ]

    if sessionStorage[user_id]['true_station']:
        res['response']['buttons'] += [
            {
                'title': 'Изменить станцию',
                'hide': True
            }
        ]

    res['response']['buttons'] += [
        {
            'title': 'Помощь',
            'hide': True
        }
    ]


# Функция на замену спец символов
def clearWord(word):
    return re.sub('[?!#;:*()-+=»«`~.,<>[]|] \t', '', word)


def normalization(lst):
    loc = []
    for item in lst:
        loc.append(clearWord(item.strip().lower()))

    return loc


if __name__ == "__main__":
    app.run()
