from flask import Flask, request
import logging
import json
import requests

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
        sessionStorage[user_id]['try'] = 0

        res['response']['text'] = 'Привет! Я могу рассказать о нужной вам станции! ' \
                                  'Скажите адрес, от которого будет происходить поиск станций.'

        set_help_buttons(user_id, res)

    else:
        # Block to show the races schedule of once station

        tokens = req['request']['nlu']['tokens']
        entities = req['request']['nlu']['entities']

        if {'изменить', 'адрес'}.issubset(tokens) or {'другой', 'адрес'}.issubset(tokens):
            # User want to edit the address (come back to begin of address select)
            sessionStorage[user_id]['transport_type'] = False
            sessionStorage[user_id]['true_address'] = False
            sessionStorage[user_id]['true_station'] = False
            sessionStorage[user_id]['geo_response'] = None
            sessionStorage[user_id]['link_to_trips'] = False
            sessionStorage[user_id]['station_type_search'] = False
            sessionStorage[user_id]['nearest_stations_buttons'] = False
            sessionStorage[user_id]['test'] = True
            sessionStorage[user_id]['date'] = False
            sessionStorage[user_id]['try'] = 0

            res['response']['text'] = 'Скажите адрес, от которого будет происходить поиск станций'

        elif {'изменить', 'тип', 'транспорта'}.issubset(tokens) or {'изменить', 'транспорт'}.issubset(tokens):
            # That data needs to clean to start searching again
            sessionStorage[user_id]['transport_type'] = True
            sessionStorage[user_id]['link_to_trips'] = False
            sessionStorage[user_id]['true_station'] = False
            sessionStorage[user_id]['date'] = False
            sessionStorage[user_id]['nearest_stations_buttons'] = False
            sessionStorage[user_id]['station_type_search'] = False

            res['response']['text'] = 'Выберите тип транспорта.'

        elif {'изменить', 'станцию'}.issubset(tokens) or {'другую', 'станцию'}.issubset(tokens):
            sessionStorage[user_id]['true_station'] = False
            sessionStorage[user_id]['date'] = False
            sessionStorage[user_id]['nearest_stations_buttons'] = False

            receive_stations(user_id, res)

        elif {'самолёт', 'поезд', 'электричка', 'автобус', 'морской', 'вертолёт'}.intersection(tokens):
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

            sessionStorage[user_id]['transport_type_req'] = types[str(list(
                {'самолёт', 'поезд', 'электричка', 'автобус', 'морской', 'вертолёт'}.intersection(tokens))[0])]

            sessionStorage[user_id]['station_type_search'] = True
            res['response']['text'] = 'Отлично! Найти ближайшие станции или по ключевому слову?'

            sessionStorage[user_id]['transport_type'] = False

        elif 'ближайшие' in tokens and 'ключевому' not in tokens:
            receive_stations(user_id, res)

            sessionStorage[user_id]['station_type_search'] = False

        elif not sessionStorage[user_id]['true_address']:
            # User didn't wrote a name of station yet
            sessionStorage[user_id]['true_station'] = False

            handle_address(res, tokens, user_id)

        elif not sessionStorage[user_id]['true_station']:
            handle_station(res, tokens, user_id)

        else:
            # Receiving the schedule of the specified station, date and time

            if handle_datetime(res, user_id, entities):
                receive_schedule(res, user_id)
            elif {'псмотреть', 'рейсы'}.issubset(tokens):
                res['response']['text'] = 'Открываю'
            else:
                res['response']['text'] = 'Я не понимаю. Попробуйте сказать по-другому.'

        if not res['response']['end_session']:
            set_help_buttons(user_id, res)


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
           sessionStorage[user_id]['date'].replace('.', '-')

    sessionStorage[user_id]['link_to_trips'] = link

    res['response']['text'] = 'Переходите по ссылке в кнопке.'

    print(link)


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

    for station in sessionStorage[user_id]['stations_response']['stations'][:5]:
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
    res['response']['text'] = 'Указанной станции не найдено. Назовите полное имя станции.'


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


def receive_stations(user_id, res):
    sessionStorage[user_id]['true_address'] = True  # Valid address

    user_try = sessionStorage[user_id]['try']
    lng, lat = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
        user_try]["GeoObject"]["Point"]["pos"].split()

    #  Find the five nearest stations
    schedule_params = {
        'apikey': '0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a',
        'transport_types': sessionStorage[user_id]['transport_type_req'],
        'lat': lat,
        'lng': lng
    }
    sessionStorage[user_id]['stations_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/nearest_stations/",
        params=schedule_params).json()
    stations = sessionStorage[user_id]['stations_response']['stations'][:5]

    sessionStorage[user_id]['nearest_stations_buttons'] = []

    text_response = '5 ближайших станций: \n\n'
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

        res['response']['text'] = text_response
    else:
        res['response']['text'] = 'Таких станций не найдено.'


def set_help_buttons(user_id, res):
    # This function add in response help-buttons according to user status

    res['response']['buttons'] = []

    if sessionStorage[user_id]['link_to_trips'] is not False:
        res['response']['buttons'] += [
            {
                'title': 'Посмотреть рейсы',
                'url': sessionStorage[user_id]['link_to_trips'],
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


if __name__ == "__main__":
    app.run()
