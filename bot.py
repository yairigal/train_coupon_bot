import re
import os
import time
import json
import logging
import datetime
from typing import List
import logging.handlers
from functools import wraps

from telegram.ext.dispatcher import run_async
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction, InlineKeyboardButton, InlineKeyboardMarkup

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
     MAIN,
     HANDLE_ORIGIN_STATION,
     HANDLE_DEST_STATION,
     HANDLE_DATE,
     HANDLE_TRAIN,
     WHETHER_TO_CONTINUE,
     EDIT_ID,
     EDIT_PHONE,
     EDIT_EMAIL,
     SAVE_TRAIN,
     SAVED_TRAINS,
     *_) = range(256)


class TrainCouponBot:
    LOG_FILE = 'bot.log'
    USERS_FILE = 'contacts.json'

    EDIT_ID = 'Edit ID'
    EDIT_PHONE = 'Edit Phone'
    EDIT_EMAIL = 'Edit Email'
    ORDER_COUPON = 'Order a coupon'
    SAVED_TRAINS = 'Saved trains'

    MAIN_STATE_OPTIONS = [
        [EDIT_ID, EDIT_PHONE],
        [EDIT_EMAIL, ORDER_COUPON],
        [SAVED_TRAINS]
    ]

    def __init__(self, token, polling, num_threads, host, port, logger_level=logging.INFO):
        self.token = token
        self.polling = polling
        self.num_threads = num_threads
        self.host= host
        self.port = port

        # Enable logging
        self.logger = self._configure_logger(logger_level)

    def _configure_logger(self, logger_level):
        logger = logging.getLogger(__name__)
        logger.setLevel(logger_level)
        formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(self.LOG_FILE, maxBytes=2 ** 20, backupCount=2)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

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
                States.PHONE: [MessageHandler(Filters.text, self.handle_phone, pass_user_data=True)],
                States.EMAIL: [MessageHandler(Filters.text, self.handle_email, pass_user_data=True)],
                States.MAIN: [CallbackQueryHandler(self.handle_main_state, pass_user_data=True)],
                States.EDIT_ID: [MessageHandler(Filters.text, self.handle_edit_id, pass_user_data=True)],
                States.EDIT_PHONE: [MessageHandler(Filters.text, self.handle_edit_phone, pass_user_data=True)],
                States.EDIT_EMAIL: [MessageHandler(Filters.text, self.handle_edit_email, pass_user_data=True)],
                States.HANDLE_ORIGIN_STATION: [
                    MessageHandler(Filters.text, self.handle_origin_station, pass_user_data=True)],
                States.HANDLE_DEST_STATION: [MessageHandler(Filters.text, self.handle_dest_station,
                                                            pass_user_data=True)],
                States.HANDLE_TRAIN: [MessageHandler(Filters.text, self.handle_train, pass_chat_data=True)],
                States.SAVE_TRAIN: [MessageHandler(Filters.text, self.handle_save_train, pass_chat_data=True)],
                States.SAVED_TRAINS: [MessageHandler(Filters.text, self.handle_saved_trains, pass_chat_data=True)],
            },
            fallbacks=[CommandHandler('stop', self.cancel, pass_user_data=True)],

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
            self.updater.start_webhook(listen='0.0.0.0',
                                       port=self.port,
                                       url_path=self.token)
            self.updater.bot.set_webhook(url=self.host + self.token,
                                         max_connections=100)

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
            time.sleep(1)  # Telegram servers does not let you send more than 30 messages per second
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

    def _reformat_to_readable_date(self, d):
        return re.fullmatch("(.*) \d+:.*", d.ctime()).group(1)

    def _reply_message(self, update, message, keyboard: List[List[str]] = None, inline_keyboard=False):
        if keyboard is not None:
            if not inline_keyboard:
                update.message.reply_text(message,
                                          reply_markup=ReplyKeyboardMarkup(
                                              keyboard=keyboard,
                                              one_time_keyboard=True))

            else:
                kybd = [[InlineKeyboardButton(lb, callback_data=lb) for lb in lst] for lst in keyboard]
                kybd = InlineKeyboardMarkup(inline_keyboard=kybd)
                update.message.reply_text(message,
                                          reply_markup=kybd)

        else:
            update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())

    def _reply_train_summary(self, update, context):
        origin_station = train_api.train_station_id_to_name(context.user_data['origin_station_id'])
        dest_station = train_api.train_station_id_to_name(context.user_data['dest_station_id'])
        selected_date = self._reformat_to_readable_date(context.user_data['date'])
        self._reply_message(update,
                            f'Displaying trains for\n'
                            f'{origin_station} -> {dest_station}\n'
                            f'on {selected_date}',
                            keyboard=[[i] for i in context.user_data['trains'].keys()])

    def _prompt_main_menu(self, update, context, message='Please choose an option:'):
        self._reply_message(update,
                            f'ID: {context.user_data["id"]}\n'
                            f'Phone: {context.user_data["phone"]}\n'
                            f'Email: {context.user_data["email"]}\n'
                            f'{message}',
                            keyboard=self.MAIN_STATE_OPTIONS,
                            inline_keyboard=True)

    def _replay_coupon(self, context, current_train, image_path, update):
        origin_station = train_api.train_station_id_to_name(int(current_train['OrignStation']))
        dest_station = train_api.train_station_id_to_name(int(current_train['DestinationStation']))
        train_date = context.user_data['date']
        train_times = train_api.get_train_printable_travel_time(current_train)
        self._reply_message(update,
                            f"Coupon for train #{current_train['Trainno']}:\n"
                            f"{origin_station} -> {dest_station}\n"
                            f"{self._reformat_to_readable_date(train_date)}, {train_times}")
        with open(image_path, 'rb') as f:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(f)

        context.user_data['last_train'] = current_train

    @staticmethod
    def _saved_trains(context, printable=False):
        if 'saved_trains' not in context.user_data:
            context.user_data['saved_trains'] = []

        if not printable:
            return context.user_data['saved_trains']

        train_list = {}
        for train in context.user_data['saved_trains']:
            origin_station = train_api.train_station_id_to_name(int(train['OrignStation']))
            dest_station = train_api.train_station_id_to_name(int(train['DestinationStation']))
            train_times = train_api.get_train_printable_travel_time(train)
            text = f"{origin_station} -> {dest_station}, {train_times}"
            train_list[text] = train

        return train_list

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
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! ID is {user_id}. Please enter your phone number')
        return States.PHONE

    @log_user
    def handle_phone(self, update, context):
        phone = update.message.text
        if not self._phone_valid(phone):
            self._reply_message(update, 'phone number is not valid, please enter valid phone number')
            return States.PHONE

        context.user_data['phone'] = phone
        self._reply_message(update, f'Success! phone number is {phone}. Please enter your email address')
        return States.EMAIL

    @log_user
    def handle_email(self, update, context):
        email = update.message.text
        if not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EMAIL

        context.user_data['email'] = email
        self._prompt_main_menu(update, context)
        return States.MAIN

    def handle_main_state(self, update, context):
        option = update.callback_query
        option.answer()

        if option.data == self.EDIT_ID:
            option.edit_message_text(text="Enter new ID")
            return States.EDIT_ID

        if option.data == self.EDIT_PHONE:
            option.edit_message_text(text='Enter new phone number')
            return States.EDIT_PHONE

        if option.data == self.EDIT_EMAIL:
            option.edit_message_text(text='Enter new email address')
            return States.EDIT_EMAIL

        if option.data == self.ORDER_COUPON:
            option.edit_message_text(text=self.ORDER_COUPON)
            self._reply_message(option, 'Please choose an origin station from the list below',
                                keyboard=[[i] for i in self.train_stations])
            return States.HANDLE_ORIGIN_STATION

        if option.data == self.SAVED_TRAINS:
            option.edit_message_text(text=self.SAVED_TRAINS)
            if len(self._saved_trains(context)) == 0:
                self._reply_message(option, 'No saved trains found, order first to save')
                self._prompt_main_menu(option, context)
                return States.MAIN

            self._reply_message(option,
                                'Choose a train to order from the list below',
                                keyboard=[[i] for i in self._saved_trains(context, printable=True).keys()])
            return States.SAVED_TRAINS

    @log_user
    def handle_edit_id(self, update, context):
        user_id = update.message.text
        if not self._id_valid(user_id):
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.EDIT_ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! new ID is {user_id}')
        self._prompt_main_menu(update, context)
        return States.MAIN

    @log_user
    def handle_edit_phone(self, update, context):
        phone = update.message.text
        if not self._phone_valid(phone):
            self._reply_message(update, 'phone number is not valid, please enter valid phone number')
            return States.EDIT_PHONE

        context.user_data['phone'] = phone
        self._reply_message(update, f'Success! new phone number is {phone}')
        self._prompt_main_menu(update, context)
        return States.MAIN

    @log_user
    def handle_edit_email(self, update, context):
        email = update.message.text
        if not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EDIT_EMAIL

        context.user_data['email'] = email
        self._reply_message(update, f'Success! new email address is {email}')
        self._prompt_main_menu(update, context)
        return States.MAIN

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
                            f'Success! origin station picked is {origin_station}.\n'
                            f'Please choose a destination station from the list below',
                            keyboard=[[i] for i in self.train_stations])
        return States.HANDLE_DEST_STATION

    @log_user
    @run_async
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
                trains = list(train_api.get_available_trains(origin_station_id=context.user_data['origin_station_id'],
                                                             dest_station_id=context.user_data['dest_station_id'],
                                                             date=day))
                if len(trains) > 0:
                    trains = {train_api.get_train_printable_travel_time(train): train for train in trains}
                    context.user_data['trains'] = trains
                    context.user_data['date'] = day
                    self._reply_train_summary(update, context)
                    return States.HANDLE_TRAIN

            except (ValueError, AttributeError) as e:
                self.logger.error(f'exception occurred in get_available_trains {e}')
                self._reply_message(update, 'An error occurred on the server, Please try again')
                self._prompt_main_menu(update, context)
                return States.MAIN

        else:
            self._reply_message(update, "No trains are available for the next week, closing conversation")
            self._prompt_main_menu(update,
                                   context)
            return States.MAIN

    @log_user
    @run_async
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
            self._reply_message(update, "Ordering coupon...")
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
            self._reply_train_summary(update, context)
            return States.HANDLE_TRAIN

        self._replay_coupon(context, current_train, image_path, update)

        self._reply_message(update,
                            "Save this train for faster access?",
                            keyboard=[['Yes', 'No']])
        return States.SAVE_TRAIN

    @log_user
    def handle_save_train(self, update, context):
        option = update.message.text.lower()
        if option not in ['yes', 'no']:
            self._reply_message(update, 'Please reply yes or no')
            return States.SAVE_TRAIN

        if option == 'yes':
            last_train = context.user_data['last_train']
            saved_trains = self._saved_trains(context)
            if last_train not in saved_trains:
                saved_trains.append(last_train)

            self._reply_message(update, 'Success! train added to saved trains')
            self._prompt_main_menu(update, context)
            return States.MAIN

        if option == 'no':
            self._prompt_main_menu(update, context)
            return States.MAIN

    @log_user
    def handle_saved_trains(self, update, context):
        selected_train = update.message.text
        saved_trains = self._saved_trains(context, printable=True)
        if selected_train not in saved_trains.keys():
            self._reply_message(update, "Please select a train from the list below")
            return States.SAVED_TRAINS

        selected_train = saved_trains[selected_train]
        user_id = context.user_data['id']
        user_phone = context.user_data['phone']
        user_email = context.user_data['email']
        origin_station_id = context.user_data['origin_station_id']
        dest_station_id = context.user_data['dest_station_id']
        train_departure = train_api._get_hour(selected_train['DepartureTime'])
        train_departure = datetime.time.fromisoformat(train_departure)

        now = datetime.datetime.now()
        request_train_datetime = datetime.datetime.combine(now, train_departure)
        if now > request_train_datetime:
            self._reply_message(update,
                                'Train departure time has passed',
                                keyboard=[[i] for i in self._saved_trains(context, printable=True).keys()])
            return States.SAVED_TRAINS

        try:

            available_trains = train_api.get_available_trains(origin_station_id,
                                                              dest_station_id,
                                                              date=request_train_datetime)

        except (AttributeError, ValueError) as e:
            self.logger.error(f'exception occurred in get_available_trains {e}')
            self._reply_message(update, 'Error occurred please try again')
            self._prompt_main_menu(update, context)
            return States.MAIN

        for train in available_trains:
            if train['DepartureTime'] == selected_train['DepartureTime'] \
                    and \
                    train['ArrivalTime'] == selected_train['ArrivalTime']:
                break  # This train exists

        else:  # No trains found
            self._reply_message(update, "The selected train could'nt be found, please check the official site.")
            self._prompt_main_menu(update,
                                   context)
            return States.MAIN

        try:
            train_api.request_train(user_id=user_id,
                                    mobile=user_phone,
                                    email=user_email,
                                    origin_station_id=origin_station_id,
                                    dest_station_id=dest_station_id,
                                    time_for_request=request_train_datetime,
                                    image_dest='image.jpeg')

            self._replay_coupon(context, selected_train, 'image.jpeg', update)

        except (AttributeError, ValueError, RuntimeError) as e:
            self.logger.error(f'exception occurred in request_train {e}')
            self._reply_message(update, 'Error occurred please try again')

        self._prompt_main_menu(update, context)
        return States.MAIN

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
