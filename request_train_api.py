# coding=utf-8
import json
import base64
import datetime
from json import JSONDecodeError

import requests

stations_info = {
    3700: {'Code': '3700',
           'HE': 'ת"א סבידור מרכז',
           'EN': 'Tel Aviv-Center',
           'AR': 'تل ابيب  ساڤيدور المركز',
           'RU': 'Тель-Авив-Центр',
           'ID': '1'},
    3500: {'Code': '3500',
           'HE': 'הרצלייה',
           'EN': 'Hertsliyya',
           'AR': 'هرتسليا',
           'RU': 'Герцлия',
           'ID': '2'},
    3400: {'Code': '3400',
           'HE': 'בית-יהושע',
           'EN': "Bet Yehoshu''a",
           'AR': 'بيت يهوشوع',
           'RU': 'Бейт-Иеошуа ',
           'ID': '3'},
    3300: {'Code': '3300',
           'HE': 'נתניה',
           'EN': 'Netanya',
           'AR': 'نتانيا',
           'RU': 'Нетания',
           'ID': '4'},
    3100: {'Code': '3100',
           'HE': 'חדרה מערב',
           'EN': 'Hadera- West',
           'AR': 'الخضيرة - غرب',
           'RU': 'Хадера - Маарав',
           'ID': '5'},
    2800: {'Code': '2800',
           'HE': 'בנימינה',
           'EN': 'Binyamina',
           'AR': 'بنيامينا',
           'RU': 'Биньямина',
           'ID': '6'},
    2820: {'Code': '2820',
           'HE': 'קיסריה פרדס-חנה',
           'EN': 'Caesarea P,h',
           'AR': 'قيساريا - بارديس حنا',
           'RU': 'Кейсария - Пардес-Хана',
           'ID': '7'},
    2500: {'Code': '2500',
           'HE': 'עתלית',
           'EN': 'Atlit',
           'AR': 'عتليت',
           'RU': 'Атлит',
           'ID': '8'},
    2200: {'Code': '2200',
           'HE': 'חיפה בת-גלים',
           'EN': 'Haifa-Bat Gallim',
           'AR': 'حيفا - بات چاليم',
           'RU': 'Хайфа - Бат-Галим',
           'ID': '9'},
    1300: {'Code': '1300',
           'HE': 'חוצות המפרץ',
           'EN': 'Hutsot HaMifrats',
           'AR': 'حوتسوت همفراتس',
           'RU': 'Хуцот ха-Мифрац ',
           'ID': '10'},
    700: {'Code': '700',
          'HE': 'קריית חיים',
          'EN': 'Kiryat Hayyim',
          'AR': 'كريات حاييم',
          'RU': 'Кирьят-Хаим',
          'ID': '11'},
    1400: {'Code': '1400',
           'HE': 'קריית מוצקין',
           'EN': 'Kiryat Motzkin',
           'AR': 'كريات موتسكين',
           'RU': 'Кирьят-Моцкин',
           'ID': '12'},
    1500: {'Code': '1500',
           'HE': 'עכו',
           'EN': 'Acre',
           'AR': 'عكا',
           'RU': 'Акко ',
           'ID': '13'},
    2300: {'Code': '2300',
           'HE': 'חיפה בחוף-הכרמל',
           'EN': 'Haifa H.HaKarmell',
           'AR': 'حيفا - شاطئ الكرمل',
           'RU': 'Хайфа Хоф-а-Кармель',
           'ID': '14'},
    8700: {'Code': '8700',
           'HE': 'כפר-סבא נורדאו',
           'EN': 'Kfar Sava-Nordau',
           'AR': 'كفار سابا - نورداو',
           'RU': 'Кфар Саба Нордау',
           'ID': '15'},
    1600: {'Code': '1600',
           'HE': 'נהרייה',
           'EN': 'Nahariyya',
           'AR': 'نهاريا',
           'RU': 'Наария',
           'ID': '16'},
    6500: {'Code': '6500',
           'HE': 'ירושלים - גן החיות התנכי',
           'EN': 'Jerusalem-Biblical Zoo',
           'AR': 'اورشليم  القدس  حديقة الحيوانات',
           'RU': 'Иерусалим зоопарк',
           'ID': '17'},
    6300: {'Code': '6300',
           'HE': 'בית-שמש',
           'EN': 'Bet Shemesh',
           'AR': 'بيت شيمش',
           'RU': 'Бейт Шемеш',
           'ID': '18'},
    7000: {'Code': '7000',
           'HE': 'קריית-גת',
           'EN': 'Kiryat Gat',
           'AR': 'كريات چات',
           'RU': 'Кирьят-Гат ',
           'ID': '19'},
    5000: {'Code': '5000',
           'HE': 'לוד',
           'EN': 'Lod',
           'AR': 'اللد',
           'RU': 'Лод',
           'ID': '20'},
    7300: {'Code': '7300',
           'HE': 'באר-שבע צפון',
           'EN': 'B.S. North',
           'AR': 'بئر السبع - شمال/الجامعة',
           'RU': 'Беер-Шева север',
           'ID': '21'},
    4800: {'Code': '4800',
           'HE': 'כפר חב"ד',
           'EN': 'Kfar Habbad',
           'AR': 'كفار حباد',
           'RU': 'Кфар ХАБАД',
           'ID': '22'},
    4600: {'Code': '4600',
           'HE': 'ת"א השלום',
           'EN': 'Tel Aviv - HaShalom',
           'AR': 'تل أبيب - السلام',
           'RU': 'Тель-Авив  а-Шалом',
           'ID': '23'},
    2100: {'Code': '2100',
           'HE': 'חיפה מרכז השמונה',
           'EN': 'Haifa Center',
           'AR': 'حيفا المركز - هشمونا',
           'RU': 'Хайфа Центр',
           'ID': '25'},
    5010: {'Code': '5010',
           'HE': 'רמלה',
           'EN': 'Ramla',
           'AR': 'الرملة',
           'RU': 'Рамле',
           'ID': '26'},
    8800: {'Code': '8800',
           'HE': 'ראש-העין צפון',
           'EN': "Rosh Ha''ayin North",
           'AR': 'روش هعاين - شمال',
           'RU': 'Рош-Айн север',
           'ID': '27'},
    5300: {'Code': '5300',
           'HE': 'באר-יעקב',
           'EN': "Be''er Ya''akov",
           'AR': 'بئير يعكوف',
           'RU': 'Беер-Яаков',
           'ID': '28'},
    5200: {'Code': '5200',
           'HE': 'רחובות',
           'EN': 'Rehovot',
           'AR': 'رحوڤوت',
           'RU': 'Реховот',
           'ID': '29'},
    # changed from 5400
    5410: {'Code': '5410',
           'HE': 'יבנה מזרח',
           'EN': 'Yavne East',
           'AR': 'ياڤنه - شرق',
           'RU': 'Явне',
           'ID': '30'},
    9100: {'Code': '9100',
           'HE': 'ראשל"צ הראשונים',
           'EN': 'R.HaRishonim',
           'AR': 'ريشون لتسيون - هريشونيم',
           'RU': 'Ришон ле-Цион  а-Ришоним ',
           'ID': '31'},
    5800: {'Code': '5800',
           'HE': 'אשדוד עד-הלום',
           'EN': 'Ashdod- Ad Halom',
           'AR': 'أشدود - عاد هلوم',
           'RU': 'Ашдод Ад-алом',
           'ID': '32'},
    4250: {'Code': '4250',
           'HE': 'פתח-תקווה סגולה',
           'EN': 'Petah Tikva-Sgulla',
           'AR': 'بيتح تكڤا - سچوله',
           'RU': 'Петах-Тиква  Сгула',
           'ID': '34'},
    4100: {'Code': '4100',
           'HE': 'בני ברק',
           'EN': 'Bne Brak',
           'AR': 'بني براك',
           'RU': 'Бней-Брак',
           'ID': '35'},
    3600: {'Code': '3600',
           'HE': 'ת"א אוניברסיטה',
           'EN': 'Tel Aviv University T"U',
           'AR': 'تل أبيب - الجامعة',
           'RU': 'Тель-Авив  Университет',
           'ID': '36'},
    7320: {'Code': '7320',
           'HE': 'באר-שבע מרכז',
           'EN': 'Beer Sheva- Center',
           'AR': 'بئر السبع - المركز',
           'RU': 'Беэр-Шева- Центр',
           'ID': '37'},
    1220: {'Code': '1220',
           'HE': 'מרכזית המפרץ',
           'EN': 'HaMifrats Central Station',
           'AR': 'همفراتس المركزية',
           'RU': 'Центральная станция Ха-Мифрац',
           'ID': '38'},
    # Changed from 4620
    4900: {'Code': '4900',
           'HE': 'ת"א ההגנה',
           'EN': 'Tel Aviv HaHagana',
           'AR': 'تل أبيب - ههچناه',
           'RU': 'Тель-Авив - ха-Хагана',
           'ID': '39'},
    8600: {'Code': '8600',
           'HE': 'נתב"ג',
           'EN': 'Ben Gurion Airport',
           'AR': 'مطار بن چوريون',
           'RU': 'Бен-Гурион Аэропорт',
           'ID': '40'},
    6700: {'Code': '6700',
           'HE': 'ירושלים - מלחה',
           'EN': 'Jerusalem - Malha',
           'AR': 'اورشليم  المالحة',
           'RU': 'Иерусалим - Мальха',
           'ID': '41'},
    5900: {'Code': '5900',
           'HE': 'אשקלון',
           'EN': 'Ashkelon',
           'AR': 'أشكلون',
           'RU': 'Ашкелон ',
           'ID': '42'},
    7500: {'Code': '7500',
           'HE': 'דימונה',
           'EN': 'Dimona',
           'AR': 'ديمونا',
           'RU': 'Димона',
           'ID': '43'},
    9200: {'Code': '9200',
           'HE': 'הוד-השרון סוקולוב',
           'EN': 'H.Sharon Sokolov',
           'AR': 'هود هشارون - سوكولوڤ',
           'RU': 'Од Ашарон - Соколов',
           'ID': '44'},
    4170: {'Code': '4170',
           'HE': 'קריית אריה',
           'EN': 'P.T. Kiryat Arye',
           'AR': 'بيتح تكڤا - كريات أريه',
           'RU': 'Петах Тиква  Кирьят Арье',
           'ID': '45'},
    5150: {'Code': '5150',
           'HE': 'לוד גני-אביב',
           'EN': 'Lod-Ganne Aviv',
           'AR': 'اللد - چاني أڤيڤ',
           'RU': 'Лод - Ганей Авив',
           'ID': '46'},
    8550: {'Code': '8550',
           'HE': 'להבים רהט',
           'EN': 'Lehavim-Rahat',
           'AR': 'لهاڤيم - رهط',
           'RU': 'Леавим - Рахат',
           'ID': '47'},
    300: {'Code': '300',
          'HE': 'פאתי מודיעין',
          'EN': "Pa'ate Modi'in",
          'AR': 'بأتي موديعين',
          'RU': 'Паатей Модиин',
          'ID': '48'},
    400: {'Code': '400',
          'HE': 'מודיעין מרכז',
          'EN': 'Modi\'in-Center M"C',
          'AR': 'موديعين - المركز',
          'RU': 'Модиин центр ',
          'ID': '49'},
    4640: {'Code': '4640',
           'HE': 'צומת חולון',
           'EN': 'Holon Junction',
           'AR': 'مفترق حولون',
           'RU': 'Холон - Развязка Холон',
           'ID': '50'},
    4660: {'Code': '4660',
           'HE': 'חולון וולפסון',
           'EN': 'Holon Wolfson',
           'AR': 'حولون - ڤولفسون',
           'RU': 'Холон - Вольфсон',
           'ID': '51'},
    4680: {'Code': '4680',
           'HE': 'בת-ים יוספטל',
           'EN': 'Bat Yam-Yoseftal',
           'AR': 'بات يام - يوسفطال',
           'RU': 'Бат Ям - Йосеф Таль',
           'ID': '52'},
    4690: {'Code': '4690',
           'HE': 'בת-ים קוממיות',
           'EN': 'Bat.Y-Komemiyyut',
           'AR': 'بات يام - كوميميوت',
           'RU': 'Бат Ям - Комемьют',
           'ID': '53'},
    9800: {'Code': '9800',
           'HE': 'ראשון לציון-משה דיין',
           'EN': 'R.Moshe-Dayan',
           'AR': 'ريشون لتسيون -موشي ديان',
           'RU': 'Ришон-Ле-Цион Моше Даян',
           'ID': '54'},
    9000: {'Code': '9000',
           'HE': 'יבנה מערב',
           'EN': 'Yavne West',
           'AR': 'ياڤني - غرب',
           'RU': 'Явне запад',
           'ID': '55'},
    9600: {'Code': '9600',
           'HE': 'שדרות',
           'EN': 'Sderot',
           'AR': 'سديروت',
           'RU': 'Сдерот',
           'ID': '56'},
    9650: {'Code': '9650',
           'HE': 'נתיבות',
           'EN': 'Netivot',
           'AR': 'نتيفوت',
           'RU': 'Нетивот',
           'ID': '57'},
    9700: {'Code': '9700',
           'HE': 'אופקים',
           'EN': 'Ofakim',
           'AR': 'أوفاكيم',
           'RU': 'Офаким',
           'ID': '58'},
    3310: {'Code': '3310',
           'HE': 'נתניה ספיר',
           'EN': 'NETANYA-SAPIR',
           'AR': 'نتانيا - سبير',
           'RU': 'Нетания - Сапфир',
           'ID': '59'},
    1240: {'Code': '1240',
           'HE': 'יקנעם כפר-יהושע',
           'EN': "YOKNE'AM-KFAR YEHOSHU'A",
           'AR': 'يوكنعام  كفار يهوشوع',
           'RU': 'Йокнеам - Кфар-Иегошуа',
           'ID': '60'},
    1250: {'Code': '1250',
           'HE': 'מגדל-העמק כפר-ברוך',
           'EN': "MIGDAL HA'EMEK-KFAR BARUKH",
           'AR': 'مجدال هعيمك  كفار باروخ',
           'RU': 'Мигдаль-ха-Эмек - Кфар Барух',
           'ID': '61'},
    1260: {'Code': '1260',
           'HE': 'עפולה ר.איתן',
           'EN': 'Afula R.Eitan',
           'AR': 'العفولة  ر. ايتان',
           'RU': 'Афула Р. Эйтан',
           'ID': '62'},
    1280: {'Code': '1280',
           'HE': 'בית שאן',
           'EN': "BEIT SHE'AN",
           'AR': 'بيت شآن',
           'RU': 'Бейт-Шеан',
           'ID': '63'},
    1820: {'Code': '1820',
           'HE': 'אחיהוד',
           'EN': 'Ahihud',
           'AR': 'أحيهود',
           'RU': 'Ахиуд',
           'ID': '64'},
    1840: {'Code': '1840',
           'HE': 'כרמיאל',
           'EN': 'Karmiel',
           'AR': 'كرمئيل',
           'RU': 'Кармиэль',
           'ID': '65'},
    2940: {'Code': '2940',
           'HE': 'רעננה מערב',
           'EN': "Ra'anana West",
           'AR': 'رعنانا ويست',
           'RU': 'Раанана-Вест',
           'ID': '66'},
    2960: {'Code': '2960',
           'HE': 'רעננה דרום',
           'EN': "Ra'anana South",
           'AR': 'رعنانا الجنوبية',
           'RU': 'Раанана Южный',
           'ID': '67'},
    6150: {'Code': '6150',
           'HE': 'קרית מלאכי - יואב',
           'EN': 'Kiryat Malakhi  Yoav',
           'AR': 'كريات ملاخي  يوآڤ',
           'RU': 'Кирьят Малахи-Йоав',
           'ID': '68'},
    680: {'Code': '680',
          'HE': 'ירושלים - יצחק נבון',
          'EN': 'Jerusalem - Yitzhak Navon',
          'AR': 'أورشليم  يتسحاق ناڤون',
          'RU': 'Иерусалим - Ицхак Навон',
          'ID': '69'},
    6900: {'Code': '6900',
           'HE': 'מזכרת בתיה',
           'EN': 'Mazkeret Batya',
           'AR': 'مزكيرت باتيا',
           'RU': 'Мазкерет Батья',
           'ID': '70'}}


def _get_hour(train_time):
    return train_time.split(' ')[-1].replace(":00", "")


def get_train_printable_travel_time(train_json):
    departure_hour = _get_hour(train_json['DepartureTime'])
    arrival_hour = _get_hour(train_json['ArrivalTime'])
    return (f"{departure_hour} - {arrival_hour}")


def train_station_name_to_id(train_name):
    return next(idx for idx, train in stations_info.items() if train['HE'] == train_name)


def train_station_id_to_name(train_id):
    return stations_info[train_id]['HE']


def get_all_trains_for_today(origin_station_id, dest_station_id, date: datetime.datetime = None):
    if date is None:
        date = datetime.datetime.now()

    date_formatted = str(date).split(" ")[0].replace("-", "")
    current_hour = f"0{date.hour}" if date.hour < 10 else date.hour

    url = ("https://www.rail.co.il/apiinfo/api/Plan/GetRoutes"
           f"?OId={origin_station_id}"
           f"&TId={dest_station_id}"
           f"&Date={date_formatted}"
           f"&Hour={current_hour}00"
           "&isGoing=true"
           f"&c={str(round(datetime.datetime.now().timestamp(), 3)).replace('.', '')}")
    res = requests.get(url)
    try:
        body = res.json()

    except JSONDecodeError:
        raise AttributeError('No JSON received. some of the request parameters might be wrong')

    if 'Data' not in body or 'Routes' not in body['Data']:
        raise ValueError('Received JSON has no attribute "Data" or "Routes"')

    for item in body['Data']['Routes']:
        for item2 in item['Train']:
            yield item2


def get_available_trains(origin_station_id, dest_station_id, date: datetime.datetime = None):
    now = datetime.datetime.now()
    if date is None:
        date = now

    date_formatted = str(date).split(" ")[0].replace("-", "")
    current_hour = f"0{date.hour}" if date.hour < 10 else date.hour

    url = ("https://www.rail.co.il/apiinfo/api/Plan/GetRoutes"
           f"?OId={origin_station_id}"
           f"&TId={dest_station_id}"
           f"&Date={date_formatted}"
           f"&Hour={current_hour}00"
           "&isGoing=true"
           f"&c={str(round(datetime.datetime.now().timestamp(), 3)).replace('.', '')}")
    res = requests.get(url)
    try:
        body = res.json()

    except JSONDecodeError:
        raise AttributeError('No JSON received. some of the request parameters might be wrong')

    if 'Data' not in body or 'Routes' not in body['Data']:
        raise ValueError('Received JSON has no attribute "Data" or "Routes"')

    for item in body['Data']['Routes']:
        for item2 in item['Train']:
            if _train_arrival_datetime(item2) > now:
                yield item2


def get_first_available_train(origin_station_id, dest_station_id, date):
    now = datetime.datetime.now()

    trains = get_available_trains(origin_station_id, dest_station_id, date=date)
    trains = sorted(list(trains), key=_train_arrival_datetime)
    trains = [train for train in trains if _train_arrival_datetime(train) > now]
    if len(trains) == 0:
        raise RuntimeError('No trains available found in that time')

    return trains[0]


def _decode_and_save_image(raw_b64, dest='image.jpeg'):
    image_binary = base64.b64decode(raw_b64)
    with open(dest, 'wb') as f:
        f.write(image_binary)


def _train_arrival_datetime(train):
    return datetime.datetime.strptime(train['DepartureTime'], "%d/%m/%Y %H:%M:%S")


def request_train(user_id,
                  mobile,
                  email,
                  origin_station_id=None,
                  dest_station_id=None,
                  time_for_request: datetime.datetime = None,
                  train_json=None,
                  image_dest='image.jpeg'):
    url = ("https://www.rail.co.il/taarif//_layouts/15/SolBox.Rail.FastSale/ReservedPlaceHandler.ashx"
           "?numSeats=1"
           f"&smartCard={user_id}"
           f"&mobile={mobile}"
           f"&userEmail={email}"
           "&method=MakeVoucherSeatsReservation"
           "&IsSendEmail=true"
           "&source=1"
           "&typeId=1")

    if train_json is None and (origin_station_id is None or dest_station_id is None or time_for_request is None):
        raise ValueError("Either train_json should be supplied or (origin_station_id, dest_station_id, "
                         "time_for_request)")

    if train_json is not None:
        train = train_json
        origin_station_id = int(train['OrignStation'])
        dest_station_id = int(train['DestinationStation'])

    else:
        train = get_first_available_train(origin_station_id, dest_station_id, time_for_request)

    payload = [{
        'TrainDate': f"{train['ArrivalTime'].split(' ')[0]} 00:00:00",
        'destinationStationId': stations_info[dest_station_id]['ID'],
        'destinationStationHe': '',
        'orignStationId': stations_info[origin_station_id]['ID'],
        'orignStationHe': '',
        'trainNumber': train['Trainno'],
        'departureTime': train['DepartureTime'],
        'arrivalTime': train['ArrivalTime'],
        'orignStation': stations_info[origin_station_id]['HE'],
        'destinationStation': stations_info[dest_station_id]['HE'],
        'orignStationNum': origin_station_id,
        'destinationStationNum': dest_station_id,
        'DestPlatform': train['DestPlatform'],
        'TrainOrder': 1
    }]

    res = requests.post(url, data=json.dumps(payload), headers={'en-US,en;q=0.9,he-IL;q=0.8,he;q=0.7'})
    try:
        body = res.json()

    except JSONDecodeError:
        print('crashed in json')
        with open('error.html', 'w') as f:
            print('saving error.html')
            f.write(res.content)

        print('raising attribute error')
        raise AttributeError('No JSON received, some of the arguments must be wrong')

    if 'BarcodeImage' not in body:
        raise ValueError('Cannot find BarcodeImage in the response JSON')

    image_b64_raw = body['BarcodeImage']
    if image_b64_raw is None:
        raise RuntimeError(f'barcode image is None, error is {body["ErrorDescription"]}')

    _decode_and_save_image(image_b64_raw, dest=image_dest)

    return image_dest
