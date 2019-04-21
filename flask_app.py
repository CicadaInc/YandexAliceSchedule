from flask import Flask, request
import logging
import json
import requests
from datetime import datetime

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

        # User din't wrote an address yet
        sessionStorage[user_id]['true_address'] = False
        sessionStorage[user_id]['geo_response'] = None
        sessionStorage[user_id]['true_station'] = False
        sessionStorage[user_id]['first_station'] = True
        sessionStorage[user_id]['trips'] = []
        sessionStorage[user_id]['today_date'] = None
        sessionStorage[user_id]['try'] = 0

        res['response']['text'] = 'Привет! Я могу рассказать вам о нужной вам станции! ' \
                                  'Скажите адрес, от которого будет происходить поиск станций'

        set_help_buttons(user_id, res)

    else:
        # Block to show the races schedule of once station

        tokens = req['request']['nlu']['tokens']
        entities = req['request']['nlu']['entities']

        if {'изменить', 'адрес'}.issubset(tokens) or {'другой', 'адрес'}.issubset(tokens):
            # User want to edit the address (come back to begin of address select)
            sessionStorage[user_id]['true_address'] = False
            sessionStorage[user_id]['geo_response'] = None
            sessionStorage[user_id]['first_station'] = True
            sessionStorage[user_id]['try'] = 0

            res['response']['text'] = 'Скажите адрес, от которого будет происходить поиск станций'

        elif {'изменить', 'станцию'}.issubset(tokens) or {'другую', 'станцию'}.issubset(tokens):
            sessionStorage[user_id]['true_station'] = False

            add_stations_in_response(user_id, res)

        elif {'пока', 'прощай'}.intersection(tokens) or {'до', 'скорого'}.issubset(tokens) \
                or {'до', 'свидания'}.issubset(tokens):
            # User said farewell
            res['response']['text'] = 'До встречи, землянин ;)'
            res['response']['end_session'] = True

        elif not sessionStorage[user_id]['true_address']:
            # User didn't wrote a name of station yet
            sessionStorage[user_id]['true_station'] = False

            handle_address(res, tokens, user_id)

        elif not sessionStorage[user_id]['true_station']:
            # User didn't wrote a date yet
            sessionStorage[user_id]['true_date'] = False

            handle_station(res, tokens, user_id)

        elif not sessionStorage[user_id]['true_date']:
            handle_date(res, entities, user_id)

        elif sessionStorage[user_id]['true_date']:
            # Receiving the schedule of the specified station
            handle_schedule(res, user_id)

        if not res['response']['end_session']:
            set_help_buttons(user_id, res)


def handle_schedule(res, user_id):
    schedule_params = {
        "apikey": "0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a",
        "station": sessionStorage[user_id]['station']['code'],
        "date": sessionStorage[user_id]['date']
    }

    sessionStorage[user_id]['schedule_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/schedule/",
        params=schedule_params).json()

    res['response']['text'] = ''
    sessionStorage[user_id]['trips'] = []

    # print(sessionStorage[user_id]['schedule_response']['schedule'])
    for way in sessionStorage[user_id]['schedule_response']['schedule']:
        res['response']['text'] += way['thread']['short_title'] + '\n\n'
        sessionStorage[user_id]['trips'].append(
            {
                "title": way['thread']['short_title'],
                "hide": True
            }
        )

    res['response']['text'] = res['response']['text'].rstrip('\n\n')

    sessionStorage[user_id]['today_date'] = None

    return


# Date normalization to ISO 8601
def date_normalization(day, month, year):
    if len(month) == 1:
        month = '0' + month
    if len(day) == 1:
        day = '0' + day

    return year + '-' + month + '-' + day


def handle_date(res, entities, user_id):
    for entity in entities:
        if entity['type'] == 'YANDEX.DATETIME':
            # res['response']['text'] = date_normalization(str(entity['value']['day']),
            #                                              str(entity['value']['month']),
            #                                              str(entity['value']['year']))
            sessionStorage[user_id]['date'] = date_normalization(str(entity['value']['day']),
                                                                 str(entity['value']['month']),
                                                                 str(entity['value']['year']))
            sessionStorage[user_id]['true_date'] = True

            handle_schedule(res, user_id)

            return
    res['response']['text'] = 'Я не понимаю. Попробуйте сказать по-другому.'


def handle_station(res, tokens, user_id):
    # Function to handles the sent station

    # Requested name
    station_name = ' '.join(tokens)

    for station in sessionStorage[user_id]['stations_response']['stations']:
        # Name from json-request
        station_name1 = '{} {}'.format(station['station_type_name'], station['title']).lower()
        station_name1 = ''.join([el for el in station_name1 if el == ' ' or el.isalnum()])

        if station_name1 == station_name:
            res['response']['text'] = 'Вы выбрали станцию "{}".\n' \
                                      'Теперь скажите мне нужную дату.'.format(station_name1)

            sessionStorage[user_id]['true_station'] = True
            sessionStorage[user_id]['station'] = station

            sessionStorage[user_id]['today_date'] = str(datetime.today())[:11]

            return

    # We didn't find requested station
    res['response']['text'] = 'Указанной станции не найдено. Введите полное имя станции'


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

            sessionStorage[user_id]['first_station'] = False

        except IndexError:
            sessionStorage[user_id]['geo_response'] = None
            res['response']['text'] = 'Не поняла адреса'

    elif 'да' in tokens and 'нет' not in tokens:
        # If user confirmed address

        add_stations_in_response(user_id, res)

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

            sessionStorage[user_id]['first_station'] = False

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


def add_stations_in_response(user_id, res):
    sessionStorage[user_id]['true_address'] = True  # Valid address

    user_try = sessionStorage[user_id]['try']
    lng, lat = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
        user_try]["GeoObject"]["Point"]["pos"].split()

    #  Find the five nearest stations
    schedule_params = {
        'apikey': '0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a',
        'lat': lat,
        'lng': lng
    }
    sessionStorage[user_id]['stations_response'] = requests.get(
        "https://api.rasp.yandex.net/v3.0/nearest_stations/",
        params=schedule_params).json()
    stations = sessionStorage[user_id]['stations_response']['stations'][:5]

    text_response = '5 ближайших станций: \n\n'
    for station in stations:
        distance = round(station['distance'], 3)
        text_response += '{} {}\n' \
                         'Расстояние: {} км\n\n'.format(station['station_type_name'], station['title'], distance)
    text_response += 'Скажите полное имя станции, чтобы узнать расписание ее рейсов'

    res['response']['text'] = text_response


def set_help_buttons(user_id, res):
    # This function add in response help-buttons according to user status

    res['response']['buttons'] = []

    if sessionStorage[user_id]['today_date'] is not None:
        res['response']['buttons'] += [
            {
                'title': sessionStorage[user_id]['today_date'],
                'hide': True
            }
        ]

    if len(sessionStorage[user_id]['trips']) != 0:
        res['response']['buttons'] += sessionStorage[user_id]['trips']

    if sessionStorage[user_id]['first_station']:
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

    if sessionStorage[user_id]['true_station']:
        res['response']['buttons'] += [
            {
                'title': 'Изменить станцию',
                'hide': True
            }
        ]

    res['response']['buttons'] += [
        {
            'title': 'Пока',
            'hide': True
        }
    ]


if __name__ == "__main__":
    app.run()
