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

        # User din't wrote an address yet
        sessionStorage[user_id]['true_address'] = False
        sessionStorage[user_id]['geo_response'] = None
        sessionStorage[user_id]['try'] = 0

        res['response']['text'] = 'Привет! Я могу рассказать вам о нужной вам станции! ' \
                                  'Скажите адрес, от которого будет происходить поиск станций'

    else:
        # Block to show the races schedule of once station

        tokens = req['request']['nlu']['tokens']

        if not sessionStorage[user_id]['true_address']:
            # User didn't wrote a station yet
            sessionStorage[user_id]['true_station'] = False

            handle_address(res, tokens, user_id)

        elif not sessionStorage[user_id]['true_station']:
            handle_station(res, tokens, user_id)

            # User din't wrote a date yet
            sessionStorage[user_id]['true_date'] = False

        elif not sessionStorage[user_id]['true_date']:
            handle_date(res, tokens, user_id)


def handle_date(res, tokens, user_id):
    res['response']['text'] = ' '.join(tokens)


def handle_station(res, tokens, user_id):
    # Function to handles the sent station

    # Requested name
    station_name = ' '.join(tokens)

    for station in sessionStorage[user_id]['stations_response']['stations']:
        # Name from json-request
        station_name1 = '{} {}'.format(station['station_type_name'], station['title']).lower()
        station_name1 = ''.join([el for el in station_name1 if el == ' ' or el.isalnum()])

        if station_name1 == station_name:
            res['response']['text'] = 'Вы выбрали станцию {}.\n' \
                                      'Теперь укажите нужную вам дату. Сначала скажите год.'.format(station_name1)

            sessionStorage[user_id]['true_station'] = True
            sessionStorage[user_id]['station'] = station

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

            # If user does not confirm the address we will try to get another
            sessionStorage[user_id]['try'] += 1

        except IndexError:
            sessionStorage[user_id]['geo_response'] = None
            res['response']['text'] = 'Не поняла адреса'

    elif 'да' in tokens and 'нет' not in tokens:
        # If user confirmed address

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
            text_response += '{} {}\n\n'.format(station['station_type_name'], station['title'])
        text_response += 'Скажите полное имя станции, чтобы узнать расписание ее рейсов'

        res['response']['text'] = text_response

    elif 'нет' in tokens and 'да' not in tokens:
        #  Handle the try to write address

        try:
            # Find toponym with index = try
            toponym = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
                sessionStorage[user_id]['try']]

            res['response']['text'] = 'Вы имеете ввиду этот адрес: {}?'.format(
                toponym['GeoObject']['metaDataProperty']['GeocoderMetaData']['text'])

            # If user does not confirm the address we will try to get another
            sessionStorage[user_id]['try'] += 1
            if sessionStorage[user_id]['try'] == 5:  # Too many tries
                raise IndexError

        except IndexError:
            # We cant find anymore geo objects
            res['response']['text'] = 'Уточните адрес, пожалуйста'
            sessionStorage[user_id]["geo_response"] = None

    else:
        res['response']['text'] = 'Не поняла ответа. Да или нет?'


if __name__ == "__main__":
    app.run()
