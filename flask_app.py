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
        # Block for handle the new session of user

        # Empty user_data (key = user_id)
        sessionStorage[user_id] = {}
        sessionStorage[user_id]['mode'] = None  # What ability has activated by the user

        # First response with asking location of user
        res['response']['text'] = 'Привет! Я могу показать расписание рейсов станции по адресу и ...\n' \
                                  'Что вы хотите узнать?'

    else:
        tokens = req['request']['nlu']['tokens']

        if not sessionStorage[user_id]['mode']:
            # Block to handle what user wants to activate

            if {'расписание', 'рейсов', 'станции'}.issubset(tokens):
                sessionStorage[user_id]['mode'] = 'OnceStationSchedule'

                # User didn't wrote an address yet
                sessionStorage[user_id]['true_address'] = None
                sessionStorage[user_id]['geo_response'] = None
                sessionStorage[user_id]['try'] = 0

                res['response']['text'] = 'Скажите примерный адрес станции'

            # Here will be other abilities

        elif sessionStorage[user_id]['mode'] == 'OnceStationSchedule':
            # Block to show the races schedule of once station

            if not sessionStorage[user_id]['true_address']:
                handle_address(res, tokens, user_id)

            else:
                res['response']['text'] = 'Не понимаю запроса'


def handle_address(res, tokens, user_id):
    # Function handles the request when user has written an address

    if not sessionStorage[user_id]['geo_response']:
        # First try

        address = ' '.join(tokens)

        # Form geocoder request to get coordinates of designated address
        geo_params = {
            'geocode': address,
            'format': 'json'
        }
        sessionStorage[user_id]['geo_response'] = \
            requests.get("https://geocode-maps.yandex.ru/1.x/", params=geo_params).json()["response"]

        # Find toponym with index = try
        user_try = sessionStorage[user_id]['try']
        toponym = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][user_try]

        res['response']['text'] = 'Вы имеете ввиду этот адрес: {}?'.format(
            toponym['GeoObject']['metaDataProperty']['GeocoderMetaData']['text'])

        # If user does not confirm the address we will try to get another
        sessionStorage[user_id]['try'] += 1

    elif 'да' in tokens and 'нет' not in tokens:
        # If user confirmed address

        sessionStorage[user_id]['true_address'] = True  # Valid address

        user_try = sessionStorage[user_id]['try']
        lng, lat = sessionStorage[user_id]['geo_response']['GeoObjectCollection']['featureMember'][
            user_try]["GeoObject"]["Point"]["pos"].split()

        # #  Find the nearest station
        # schedule_params = {
        #     'apikey': '0737b4ea-ad09-4db2-bbc9-fcb2ae2db11a',
        #     'lat': lat,
        #     'lng': lng
        # }
        # schedule_response = requests.get("https://api.rasp.yandex.net/v3.0/nearest_stations/",
        #                                  params=schedule_params).json()
        # logging.info(schedule_response)
        # station = schedule_response['stations'][0]
        #
        # logging.info(station['code'])
        # res['response']['text'] = station['code']
        #
        # #  We has found a right station?
        # static_maps_params = {}

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
