import os
import json
import logging
import datetime
import re
from abc import ABCMeta, abstractmethod
from functools import wraps
from typing import List

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, ConversationHandler)

import request_train_api as train_api


def log_user(handler_function):
    @wraps(handler_function)
    def wrapping_handler_function(self, update, context):
        self.logger.info(f"User {update.message.from_user.username} in {handler_function.__name__}")
        return handler_function(self, update, context)

    return wrapping_handler_function


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
    def __init__(self, state_id):
        self.state_id = state_id

    @abstractmethod
    def pre_execute(self, update, context):
        return NotImplemented

    @abstractmethod
    def on_trigger(self, update, context):
        return NotImplemented


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

        contacts[user.username] = str(user.id)

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

        for name, id in users.items():
            try:
                self.updater.bot.sendMessage(int(id), message)

            except BaseException as e:
                self.logger.debug(f'Failed to broadcase message to {name} due to {e}')

    @property
    def train_stations(self):
        return [train_info['HE'] for train_info in train_api.stations_info.values()]

    @staticmethod
    def _id_valid(id_arg):
        return re.fullmatch(r'\d+', id_arg) is not None

    @staticmethod
    def _phone_valid(phone):
        return re.fullmatch(r'\d+', phone) is not None

    @staticmethod
    def _email_valid(email):
        return re.fullmatch(r'.+@.+', email) is not None

    def _reformat_to_readable_date(self, d):
        return re.fullmatch("(.*) \d+:.*", d.ctime()).group(1)

    def _reply_message(self, update, message, keyboard: List[List[str]] = None):
        if keyboard is not None:
            update.message.reply_text(message,
                                      reply_markup=ReplyKeyboardMarkup(
                                          keyboard=keyboard,
                                          one_time_keyboard=True))

        else:
            update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())

    # Handlers
    @log_user
    def handle_start(self, update, context):
        self._save_user(update.message.from_user)
        update.message.reply_text('Please enter your ID', reply_markup=ReplyKeyboardRemove())
        return States.ID

    @log_user
    def handle_id(self, update, context):
        user_id = update.message.text
        if not self._id_valid(user_id):
            self._reply_message(update, 'id is not valid, please enter valid id')
            return States.ID

        context.user_data['id'] = user_id
        self._reply_message(update, 'Please enter your phone number')
        return States.PHONE

    @log_user
    def handle_phone(self, update, context):
        phone = update.message.text
        if not self._phone_valid(phone):
            self._reply_message(update, 'phone number is not valid, please enter valid phone number')
            return States.PHONE

        context.user_data['phone'] = phone
        update.message.reply_text('Please enter your email address', reply_markup=ReplyKeyboardRemove())
        return States.EMAIL

    @log_user
    def handle_email(self, update, context):
        email = update.message.text
        if not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EMAIL

        context.user_data['email'] = email
        self._reply_message(update,
                            'Choose origin station',
                            keyboard=[[i] for i in self.train_stations])
        return States.HANDLE_ORIGIN_STATION

    @log_user
    def handle_origin_station(self, update, context):
        origin_station = update.message.text
        if origin_station not in self.train_stations:
            self._reply_message(update,
                                'Please choose a station from the list below',
                                keyboard=[[i] for i in self.train_stations])
            return States.HANDLE_ORIGIN_STATION

        context.user_data['origin_station_id'] = train_api.train_station_name_to_id(origin_station)
        self._reply_message(update,
                            'Choose destination',
                            keyboard=[[i] for i in self.train_stations])
        return States.HANDLE_DEST_STATION

    @log_user
    def handle_dest_station(self, update, context):
        destination_station = update.message.text
        if destination_station not in self.train_stations:
            self._reply_message(update,
                                'Please choose a station from the list below',
                                keyboard=[[i] for i in self.train_stations])
            return States.HANDLE_DEST_STATION

        context.user_data['dest_station_id'] = train_api.train_station_name_to_id(destination_station)

        for day in self._next_week:
            try:
                trains = train_api.get_available_trains(origin_station_id=context.user_data['origin_station_id'],
                                                        dest_station_id=context.user_data['dest_station_id'],
                                                        date=day)

                if len(trains) > 0:
                    trains = {f"{train['DepartureTime'].split(' ')[-1]} - {train['ArrivalTime'].split(' ')[-1]}": train
                              for train in trains}
                    context.user_data['trains'] = trains
                    self._reply_message(update,
                                        f'Displaying trains for {self._reformat_to_readable_date(day)}',
                                        keyboard=[[i] for i in trains.keys()])
                    return States.HANDLE_TRAIN

            except (ValueError, AttributeError):
                self._reply_message(update,
                                    'An error occurred on the server, Please try again')
                return self.handle_start(update, context)

        else:
            self._reply_message(update,
                                "No trains are available for the next week, closing conversation")
            return self.cancel(update, context)

    @log_user
    def handle_train(self, update, context):
        train_date = update.message.text
        if train_date not in context.user_data['trains'].keys():
            self._reply_message(update,
                                'Please select a train from the list below',
                                keyboard=[[i] for i in context.user_data['trains'].keys()])
            return States.HANDLE_TRAIN

        current_train = context.user_data['trains'][train_date]

        image_path = 'image.jpeg'
        try:
            train_api.request_train(user_id=context.user_data['id'],
                                    mobile=context.user_data['phone'],
                                    email=context.user_data['email'],
                                    train_json=current_train,
                                    image_dest=image_path)

        except AttributeError:
            # error with the arguments passed
            self._reply_message(update,
                                'Error occurred in the server, some details might be wrong, please enter them again')
            return self.handle_start(update, context)

        except (ValueError, RuntimeError) as e:
            # No bardcode image found
            self.logger.error(f'no barcode image received, error={e}')
            self._reply_message(update,
                                'No barcode image received from the server. This might happen if the same seat is '
                                'ordered twice. Please pick another seat')
            self._reply_message(update,
                                f'Please choose different train',
                                keyboard=[[i] for i in context.user_data['trains'].keys()])
            return States.HANDLE_TRAIN

        with open(image_path, 'rb') as f:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(f)

        self._reply_message(update,
                            'Get another coupon?',
                            keyboard=[['Order Different Train'], ['Order the same', 'Close']])

        return States.WHETHER_TO_CONTINUE

    @log_user
    def handle_whether_to_continue(self, update, context):
        answer = update.message.text
        if answer not in ['Order Different Train', 'Order the same', 'Close']:
            self._reply_message(update,
                                'Please choose a valid option',
                                keyboard=[['Order Different Train'], ['Order the same', 'Close']])
            return States.WHETHER_TO_CONTINUE

        if answer == 'Order Different Train':
            self._reply_message(update,
                                'Choose origin station',
                                keyboard=[[i] for i in self.train_stations])
            return States.HANDLE_ORIGIN_STATION

        elif answer == 'Order the same':
            self._reply_message(update,
                                f'Please choose a train',
                                keyboard=[[i] for i in context.user_data['trains'].keys()])
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
