import base64
import datetime
import json
import os
import re
from json import JSONDecodeError
from operator import attrgetter

import requests

MOBILE_PLACEHOLDER = "0123456789"

proxies = {'https': os.getenv('RAIL_PROXY')}

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


class Train:
    def __init__(self,
                 departure_time: datetime.datetime,
                 arrival_time: datetime.datetime,
                 origin_station_id: int,
                 destination_station_id: int,
                 train_number: int,
                 destination_platform: int,
                 platform: int,
                 is_full_train):
        self.departure_datetime = departure_time
        self.arrival_datetime = arrival_time
        self.origin_station_id = origin_station_id
        self.destination_station_id = destination_station_id
        self.train_number = train_number
        self.destination_platform = destination_platform
        self.platform = platform
        self.is_full_train = is_full_train

    @classmethod
    def from_json(cls, train_dict):
        arrival_time = Train._train_arrival_datetime(train_dict["ArrivalTime"])
        departure_time = Train._train_arrival_datetime(train_dict["DepartureTime"])
        return cls(departure_time=departure_time,
                   arrival_time=arrival_time,
                   origin_station_id=int(train_dict["OrignStation"]),
                   destination_station_id=int(train_dict["DestinationStation"]),
                   train_number=int(train_dict["Trainno"]),
                   destination_platform=int(train_dict["DestPlatform"]),
                   platform=int(train_dict['Platform']),
                   is_full_train=train_dict["IsFullTrain"])

    def get_printable_travel_time(self):
        return f"{self.departure_time} - {self.arrival_time}"

    @staticmethod
    def _get_hour(train_time):
        return train_time.split(' ')[-1].replace(":00", "")

    @staticmethod
    def _train_arrival_datetime(train_time):
        return datetime.datetime.strptime(train_time, "%d/%m/%Y %H:%M:%S")

    @property
    def arrival_time(self):
        return self.arrival_datetime.time().strftime("%H:%M")

    @property
    def arrival_date(self):
        return self.arrival_datetime.date().strftime("%d/%m/%Y")

    @property
    def departure_time(self):
        return self.departure_datetime.time().strftime("%H:%M")

    @property
    def departure_date(self):
        return self.departure_datetime.date().strftime("%d/%m/%Y")

    @property
    def printable_arrival_time(self):
        return f"{self.arrival_date} {self.arrival_time}:00"

    @property
    def printable_departure_time(self):
        return f"{self.departure_date} {self.departure_time}:00"

    def to_dict(self):
        return {
            "DepartureTime": self.printable_departure_time,
            'ArrivalTime': self.printable_arrival_time,
            'OrignStation': self.origin_station_id,
            "DestinationStation": self.destination_station_id,
            "Trainno": self.train_number,
            "DestPlatform": self.destination_platform
        }

    def __str__(self):
        origin_station_name = train_station_id_to_name(self.origin_station_id)
        destination_station_name = train_station_id_to_name(self.destination_station_id)
        train_date_readable = re.fullmatch("(.*) \d+:.*", self.departure_datetime.ctime()).group(1)
        train_time_readable = self.get_printable_travel_time()
        return (f"Train #{self.train_number}:\n"
                f"{origin_station_name} -> {destination_station_name}\n"
                f"{train_date_readable}, {train_time_readable}")

    def one_line_description(self):
        origin_station = train_station_id_to_name(self.origin_station_id)
        dest_station = train_station_id_to_name(self.destination_station_id)
        train_times = self.get_printable_travel_time()
        return f"{origin_station} -> {dest_station}, {train_times}"


def train_station_name_to_id(train_name):
    return next(idx for idx, train in stations_info.items() if train['HE'] == train_name)


def train_station_id_to_name(train_id):
    return stations_info[train_id]['HE']


def get_all_trains_for_today(origin_station_id, dest_station_id, date: datetime.datetime = None):
    """Get a generator of all the trains that were available today, from 00:00 to 00:00.

    Args:
        origin_station_id (number): the origin station id.
        dest_station_id (number): the destination station id.
        date (datetime.datetime): Optional. the date of the day, the time does not matter. if not supplied the date
            is today.

    Yields:
        Train. train object contains all the data of the train.

    Raises:
        AttributeError: If some of the parameters are wrong.
        ValueError: The result from the server is missing.
    """
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
            yield Train.from_json(item2)


def get_available_trains(origin_station_id, dest_station_id, date: datetime.datetime = None):
    """Get a generator of all the train that are available from the current date and on.

    Args:
        origin_station_id (number): the origin station id.
        dest_station_id (number): the destination station id.
        date (datetime.datetime): Optional. the day and time to get ongoing trains and on. if not supplied the date
            is now.

    Yields:
        Train. train object contains all the data of the train.
    """
    now = datetime.datetime.now()
    for train in get_all_trains_for_today(origin_station_id, dest_station_id, date):
        if train.departure_datetime > now:
            yield train


def get_first_available_train(origin_station_id, dest_station_id, date):
    """Get first train available.

    Args:
        origin_station_id (number): the origin station id.
        dest_station_id (number): the destination station id.
        date (datetime.datetime): Optional. the day and time to get ongoing trains and on. if not supplied the date
            is now.

    Returns:
        Train. the first available train for that date.

    Raises:
        RuntimeError: if no trains were available for that date.
    """
    now = datetime.datetime.now()
    trains = get_available_trains(origin_station_id, dest_station_id, date=date)
    trains = sorted(list(trains), key=attrgetter('departure_datetime'))
    trains = [train for train in trains if train.departure_datetime > now]
    if len(trains) == 0:
        raise RuntimeError('No trains available found in that time')

    return trains[0]


def request_train(user_id,
                  email='',
                  origin_station_id=None,
                  dest_station_id=None,
                  time_for_request: datetime.datetime = None,
                  train_instance=None,
                  image_dest='image.jpeg'):
    """Get a QR code for a specific train.

    Args:
        user_id (str): user ID number.
        email (str): Optional. the email the server will send verification mail and cancellation link.
        origin_station_id (number): the origin station id.
        dest_station_id (number): the destination station id.
        time_for_request (datetime.datetime): Optional. the day and time for the train. if not supplied the date
            is now.
        train_instance (Train): Optional. can be passed instead of origin_station_id, dest_station_id and
            time_for_request.
        image_dest (str): Optional. path where to save the QR code image.

    Note:
        Either supply origin_station_id, dest_station_id and time_for_request or train_instance. not both and not
        none of them.

    Raises:
        AttributeError: some arguments must be wrong.
        ValueError: No barcode image received.
        RuntimeError: some other error.
    """
    url = ("https://www.rail.co.il/taarif//_layouts/15/SolBox.Rail.FastSale/ReservedPlaceHandler.ashx"
           "?numSeats=1"
           f"&smartCard={user_id}"
           f"&mobile={MOBILE_PLACEHOLDER}"
           f"&userEmail={email}"
           "&method=MakeVoucherSeatsReservation"
           "&IsSendEmail=true"
           "&source=1"
           "&typeId=1")

    if train_instance is None and (origin_station_id is None or dest_station_id is None or time_for_request is None):
        raise ValueError("Either train_json should be supplied or (origin_station_id, dest_station_id, "
                         "time_for_request)")

    if train_instance is not None:
        train = train_instance

    else:
        train = get_first_available_train(origin_station_id, dest_station_id, time_for_request)

    payload = [{
        'TrainDate': f"{train.arrival_date} 00:00:00",
        'destinationStationId': stations_info[train.destination_station_id]['ID'],
        'destinationStationHe': '',
        'orignStationId': stations_info[train.origin_station_id]['ID'],
        'orignStationHe': '',
        'trainNumber': train.train_number,
        'departureTime': train.printable_departure_time,
        'arrivalTime': train.printable_arrival_time,
        'orignStation': stations_info[train.origin_station_id]['HE'],
        'destinationStation': stations_info[train.destination_station_id]['HE'],
        'orignStationNum': train.origin_station_id,
        'destinationStationNum': train.destination_station_id,
        'DestPlatform': train.destination_platform,
        'TrainOrder': 1
    }]

    res = requests.post(url, data=json.dumps(payload), proxies=proxies, timeout=60)
    try:
        body = res.json()

    except JSONDecodeError:
        raise AttributeError('No JSON received, some of the arguments must be wrong')
        
    if 'BarcodeImage' not in body:
        raise ValueError('Cannot find BarcodeImage in the response JSON')

    image_b64_raw = body['BarcodeImage']
    if image_b64_raw is None:
        raise RuntimeError(f'barcode image is None, error is `{body["voutcher"]["ErrorDescription"]}`')

    image_binary = base64.b64decode(image_b64_raw)
    with open(image_dest, 'wb') as f:
        f.write(image_binary)

    return image_dest
