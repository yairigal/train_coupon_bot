import re
import os
import json
import logging
import datetime
from typing import List
from functools import wraps
from abc import ABCMeta, abstractmethod

from telegram.ext.dispatcher import run_async
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

import request_train_api as train_api


def log_user(handler_function):
    @wraps(handler_function)
    def wrapping_handler_function(self, update, context):
        self.logger.info(f"User {update.message.from_user.username} in {handler_function.__name__}")
        return handler_function(self, update, context)

    return wrapping_handler_function


def reply_message(update, message, keyboard: List[List[str]] = None):
    if keyboard is not None:
        update.message.reply_text(message,
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=keyboard,
                                      one_time_keyboard=True))

    else:
        update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())


class States:
    (ID,
     PHONE,
     EMAIL,
     HANDLE_ORIGIN_STATION,
     HANDLE_DEST_STATION,
     HANDLE_DATE,
     HANDLE_TRAIN,
     WHETHER_TO_CONTINUE,
     *_) = range(100)


class State(metaclass=ABCMeta):
    STATE_NUMBER = NotImplemented

    def __init__(self, bot):
        self.bot = bot

    @abstractmethod
    def pre_execute(self, update, context, *args, **kwargs):
        return NotImplemented

    @abstractmethod
    def validate_input(self, user_input):
        return NotImplemented

    @abstractmethod
    def on_invalid_input(self, update, context, *args, **kwargs):
        return NotImplemented

    @abstractmethod
    def on_trigger(self, update, context, *args, **kwargs):
        return NotImplemented


class IdState(State):
    STATE_NUMBER = States.ID

    def pre_execute(self, update, context, *args, **kwargs):
        reply_message(update, message='Please enter your ID')

    def validate_input(self, id_arg):
        return re.fullmatch(r'\d+', id_arg) is not None

    def on_invalid_input(self, update, context, *args, **kwargs):
        reply_message(update, 'ID is not valid, please enter valid ID')

    def on_trigger(self, update, context, *args, **kwargs):
        context.user_data['id'] = args[0]


class PhoneState(State):
    STATE_NUMBER = States.PHONE

    def pre_execute(self, update, context, *args, **kwargs):
        reply_message(update, f'Success! ID is {args[0]}. Please enter your phone number')

    def validate_input(self, phone):
        return re.fullmatch(r'\d+', phone) is not None

    def on_invalid_input(self, update, context, *args, **kwargs):
        reply_message(update, 'phone number is not valid, please enter valid phone number')

    def on_trigger(self, update, context, *args, **kwargs):
        context.user_data['phone'] = args[0]


class EmailState(State):
    STATE_NUMBER = States.EMAIL

    def pre_execute(self, update, context, *args, **kwargs):
        phone = context.user_data['phone']
        reply_message(update, f'Success! phone number is {phone}. Please enter your email address')

    def validate_input(self, email):
        return re.fullmatch(r'.+@.+', email) is not None

    def on_invalid_input(self, update, context, *args, **kwargs):
        reply_message(update, 'email is not valid, please enter valid email address')

    def on_trigger(self, update, context, *args, **kwargs):
        context.user_data['email'] = args[0]


class OriginStationState(State):
    STATE_NUMBER = States.HANDLE_ORIGIN_STATION

    @property
    def train_stations(self):
        return self.bot.train_stations

    def pre_execute(self, update, context, *args, **kwargs):
        email = context.user_data['email']
        reply_message(update,
                      f'Success! email address is {email}. Please choose an origin station from the list below',
                      keyboard=[[i] for i in self.train_stations])

    def validate_input(self, origin_station):
        return origin_station in self.train_stations

    def on_invalid_input(self, update, context, *args, **kwargs):
        reply_message(update,
                      'Please choose a station from the list below',
                      keyboard=[[i] for i in self.train_stations])

    def on_trigger(self, update, context, *args, **kwargs):
        context.user_data['origin_station_id'] = train_api.train_station_name_to_id(args[0])


class DestinationStationState(State):
    STATE_NUMBER = States.HANDLE_DEST_STATION

    @property
    def train_stations(self):
        return self.bot.train_stations

    def pre_execute(self, update, context, *args, **kwargs):
        reply_message(update,
                      f'Success! origin station picked is {args[0]}.\n'
                      f'Please choose a destination station from the list below',
                      keyboard=[[i] for i in self.train_stations])

    def validate_input(self, destination_station):
        return destination_station in self.train_stations

    def on_invalid_input(self, update, context, *args, **kwargs):
        reply_message(update,
                      'Please choose a station from the list below',
                      keyboard=[[i] for i in self.train_stations])

    def on_trigger(self, update, context, *args, **kwargs):
        context.user_data['dest_station_id'] = train_api.train_station_name_to_id(args[0])
        for day in self.bot._next_week:
            try:
                trains = list(train_api.get_available_trains(origin_station_id=context.user_data['origin_station_id'],
                                                             dest_station_id=context.user_data['dest_station_id'],
                                                             date=day))
                if len(trains) > 0:
                    trains = {
                        f"{self.bot._get_hour(train['DepartureTime'])} - {self.bot._get_hour(train['ArrivalTime'])}":
                            train for train in trains}
                    context.user_data['trains'] = trains
                    context.user_data['date'] = day
                    self.bot._reply_train_summary(update, context)
                    return States.HANDLE_TRAIN

            except (ValueError, AttributeError):
                reply_message(update, 'An error occurred on the server, Please try again')
                return self.handle_start(update, context)

        else:
            self.reply_message(update,
                               "No trains are available for the next week, closing conversation")
            return self.cancel(update, context)


class TrainCouponBot:
    USERS_FILE = 'contacts.json'

    def __init__(self, token, polling, num_threads, port, logger_level=logging.INFO):
        self.token = token
        self.polling = polling
        self.num_threads = num_threads
        self.port = port

        # Enable logging
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logger_level)
        self.logger = logging.getLogger(__name__)

        self.id_state = IdState(bot=self)
        self.phone_state = PhoneState(bot=self)
        self.email_state = EmailState(bot=self)
        self.origin_station_state = OriginStationState(bot=self)
        self.destination_station_state = DestinationStationState(bot=self)

    def run(self):
        # Create the EventHandler and pass it your bot's token.
        self.updater = Updater(self.token, workers=self.num_threads, use_context=True)

        # Get the dispatcher to register handlers
        dp = self.updater.dispatcher

        # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.handle_start)],
            states={
                States.ID: [MessageHandler(Filters.text, self.handle_id, pass_user_data=True)],
                States.EMAIL: [MessageHandler(Filters.text, self.handle_email, pass_user_data=True)],
                States.PHONE: [MessageHandler(Filters.text, self.handle_phone, pass_user_data=True)],
                States.HANDLE_ORIGIN_STATION: [
                    MessageHandler(Filters.text, self.handle_origin_station, pass_user_data=True)],
                States.HANDLE_DEST_STATION: [MessageHandler(Filters.text, self.handle_dest_station,
                                                            pass_user_data=True)],
                States.HANDLE_TRAIN: [MessageHandler(Filters.text, self.handle_train, pass_chat_data=True)],
                States.WHETHER_TO_CONTINUE: [MessageHandler(Filters.text, self.handle_whether_to_continue,
                                                            pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel, pass_user_data=True)],

            allow_reentry=True
        )

        dp.add_handler(conv_handler)

        # log all errors
        # dp.add_error_handler(error)

        # Start the Bot
        if self.polling:
            self.updater.start_polling()

        else:
            # webhook
            # updater.start_webhook(listen='127.0.0.1',
            #                       port=self.port,
            #                       url_path=URL_PATH + self.token)
            # updater.bot.set_webhook(url=BASE_URL + URL_PATH + self.token,
            #                         max_connections=100)
            pass

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        self.logger.info(f"Bot started running, polling={self.polling}, number of threads={self.num_threads}, "
                         f"port={self.port}")
        self.updater.idle()

    def _save_user(self, user):
        if not os.path.exists(self.USERS_FILE):
            # Create an empty json file
            with open(self.USERS_FILE, "w") as cts:
                cts.write("{}")

        with open(self.USERS_FILE) as cts:
            contacts = json.load(cts)

        contacts[user.id] = user.username

        with open(self.USERS_FILE, "w") as cts:
            json.dump(contacts, cts, indent=4)

    @property
    def _next_week(self):
        now = datetime.datetime.now()
        for i in range(7):
            yield now + datetime.timedelta(i)

    def _broadcast_message_to_users(self, message):
        self.logger.info(f"Broadcasting message `{message}`")
        with open(self.USERS_FILE) as f:
            users = json.load(f)

        for id, name in users.items():
            try:
                self.updater.bot.sendMessage(int(id), message)

            except BaseException as e:
                self.logger.debug(f'Failed to broadcast message to {name} due to {e}')

    @property
    def train_stations(self):
        return sorted([train_info['HE'] for train_info in train_api.stations_info.values()])

    @staticmethod
    def _id_valid(id_arg):
        return re.fullmatch(r'\d+', id_arg) is not None

    @staticmethod
    def _phone_valid(phone):
        return re.fullmatch(r'\d+', phone) is not None

    @staticmethod
    def _email_valid(email):
        return re.fullmatch(r'.+@.+', email) is not None

    def _get_hour(self, train_time):
        return train_time.split(' ')[-1].replace(":00", "")

    def _reformat_to_readable_date(self, d):
        return re.fullmatch("(.*) \d+:.*", d.ctime()).group(1)

    def _reply_train_summary(self, update, context):
        origin_station = train_api.train_station_id_to_name(context.user_data['origin_station_id'])
        dest_station = train_api.train_station_id_to_name(context.user_data['dest_station_id'])
        selected_date = self._reformat_to_readable_date(context.user_data['date'])
        self.reply_message(update,
                           f'Displaying trains for\n'
                           f'{origin_station} -> {dest_station}\n'
                           f'on {selected_date}',
                           keyboard=[[i] for i in context.user_data['trains'].keys()])

    # Handlers
    @log_user
    def handle_start(self, update, context):
        self._save_user(update.message.from_user)
        self.id_state.pre_execute(update, context)
        return States.ID

    @log_user
    def handle_id(self, update, context):
        user_id = update.message.text
        if not self.id_state.validate_input(user_id):
            self.id_state.on_invalid_input(update, context)
            return States.ID

        self.id_state.on_trigger(update, context)
        self.phone_state.pre_execute(update, context)
        return States.PHONE

    @log_user
    def handle_phone(self, update, context):
        phone = update.message.text
        if not self.phone_state.validate_input(phone):
            self.phone_state.on_invalid_input(update, context)
            return States.PHONE

        self.phone_state.on_trigger(update, context, phone)
        self.email_state.pre_execute(update, context)
        return States.EMAIL

    @log_user
    def handle_email(self, update, context):
        email = update.message.text
        if not self.email_state.validate_input(email):
            self.email_state.on_invalid_input(update, context)
            return States.EMAIL

        self.email_state.on_trigger(update, context, email)
        self.origin_station_state.pre_execute(update, context)
        return States.HANDLE_ORIGIN_STATION

    @log_user
    def handle_origin_station(self, update, context):
        origin_station = update.message.text
        if not self.origin_station_state.validate_input(origin_station):
            self.origin_station_state.on_invalid_input(update, context)
            return States.HANDLE_ORIGIN_STATION

        self.origin_station_state.on_trigger(update, context, origin_station)
        self.destination_station_state.pre_execute(update, context, origin_station)
        return States.HANDLE_DEST_STATION

    @log_user
    @run_async
    def handle_dest_station(self, update, context):
        destination_station = update.message.text
        if not self.destination_station_state.validate_input(destination_station):
            self.destination_station_state.on_invalid_input(update, context)
            return States.HANDLE_DEST_STATION

        return self.destination_station_state.on_trigger(update, context, destination_station)

    @log_user
    @run_async
    def handle_train(self, update, context):
        train_date = update.message.text
        if train_date not in context.user_data['trains'].keys():
            self.reply_message(update,
                               'Please select a train from the list below',
                               keyboard=[[i] for i in context.user_data['trains'].keys()])
            return States.HANDLE_TRAIN

        current_train = context.user_data['trains'][train_date]

        image_path = 'image.jpeg'
        try:
            self.reply_message(update, "Ordering coupon...")
            train_api.request_train(user_id=context.user_data['id'],
                                    mobile=context.user_data['phone'],
                                    email=context.user_data['email'],
                                    train_json=current_train,
                                    image_dest=image_path)

        except AttributeError:
            # error with the arguments passed
            self.reply_message(update,
                               'Error occurred in the server, some details might be wrong, please enter them again')
            return self.handle_start(update, context)

        except (ValueError, RuntimeError) as e:
            # No bardcode image found
            self.logger.error(f'no barcode image received, error={e}')
            self.reply_message(update,
                               'No barcode image received from the server. This might happen if the same seat is '
                               'ordered twice. Please pick another seat')
            self._reply_train_summary(update, context)
            return States.HANDLE_TRAIN

        with open(image_path, 'rb') as f:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(f)

        self.reply_message(update,
                           'Get another coupon?',
                           keyboard=[['Order Different Train'], ['Order the same', 'Close']])

        return States.WHETHER_TO_CONTINUE

    @log_user
    def handle_whether_to_continue(self, update, context):
        answer = update.message.text
        if answer not in ['Order Different Train', 'Order the same', 'Close']:
            self.reply_message(update,
                               'Please choose a valid option',
                               keyboard=[['Order Different Train'], ['Order the same', 'Close']])
            return States.WHETHER_TO_CONTINUE

        if answer == 'Order Different Train':
            self.reply_message(update,
                               'Choose origin station',
                               keyboard=[[i] for i in self.train_stations])
            return States.HANDLE_ORIGIN_STATION

        elif answer == 'Order the same':
            self._reply_train_summary(update, context)
            return States.HANDLE_TRAIN

        return self.cancel(update, context)

    @log_user
    def cancel(self, update, context):
        user = update.message.from_user
        self.logger.info("User %s canceled the conversation.", user.username)
        update.message.reply_text('Goodbye !', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


if __name__ == '__main__':
    with open('config.json', encoding='utf8') as config_file:
        config = json.load(config_file)

    # Read token
    with open("token") as token_file:
        token = token_file.read().strip('\n')

    TrainCouponBot(token=token, **config).run()
