import datetime
import json
import logging
import logging.handlers
import os
import re
import time
import traceback
from functools import wraps
from typing import List

from firebase import firebase
from telegram import ChatAction
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from telegram.ext.dispatcher import run_async

import train_api as train_api
from firebasepersistance import FirebasePersistence


def log_user(handler_function):
    @wraps(handler_function)
    def wrapping_handler_function(self, update, context):
        self.logger.info(f"User {update.message.from_user.username} in {handler_function.__name__}")
        return handler_function(self, update, context)

    return wrapping_handler_function


def handle_back(handle_state_function):
    @wraps(handle_state_function)
    def handler_wrapper(bot_obj, update, context, *args, **kwargs):
        if hasattr(update, 'message') and update.message.text == bot_obj.BACK:
            return bot_obj._move_to_main_state(update, context)

        return handle_state_function(bot_obj, update, context, *args, **kwargs)

    return handler_wrapper


def move_to_main_on_error(handler_function):
    @wraps(handler_function)
    def wrapper(self, update, context):
        try:
            return handler_function(self, update, context)

        except:
            self._reply_message(update, "General error occurred")
            raise

        finally:
            return self._move_to_main_state(update, context)

    return wrapper


class States:
    (ID,
     EMAIL,
     MAIN,
     HANDLE_ORIGIN_STATION,
     HANDLE_DEST_STATION,
     HANDLE_DATE,
     HANDLE_TRAIN,
     WHETHER_TO_CONTINUE,
     EDIT_ID,
     EDIT_EMAIL,
     SAVE_TRAIN,
     SAVED_TRAINS,
     BROADCAST,
     DELETE_SAVED_TRAIN,
     *_) = range(256)


class TrainCouponBot:
    LOG_FILE = 'bot.log'
    USERS_KEY = 'users'

    EDIT_ID = 'Edit ID'
    EDIT_EMAIL = 'Edit Email'
    ORDER_COUPON = 'Order a coupon'
    SAVED_TRAINS = 'Saved trains'
    REMOVE_SAVED_TRAINS = 'Delete saved train'

    BACK = 'Return to main menu'

    DONE_COMMAND = 'done'

    WELCOME_MESSAGE = "Welcome to Train Voucher bot,\n" \
                      "First, i need our details (Don't worry they are used only for the voucher)"

    MAIN_STATE_OPTIONS = [
        [EDIT_ID, EDIT_EMAIL],
        [ORDER_COUPON],
        [SAVED_TRAINS, REMOVE_SAVED_TRAINS]
    ]

    def __init__(self, token, polling, num_threads, port, firebase_url, admins=None, host='127.0.0.1',
                 logger_level=logging.INFO):
        self.token = token
        self.polling = polling
        self.num_threads = num_threads
        self.host = host
        self.port = port
        self.firebase_url = firebase_url
        if admins is None:
            admins = []

        self.admins = admins
        self.logger = self._configure_logger(logger_level)
        self.firebase = firebase.FirebaseApplication(self.firebase_url)

        # wrap all handlers
        for state, handler_list in self.states.items():
            for handler in handler_list:
                handler.callback = log_user(handler.callback)
                handler.callback = move_to_main_on_error(handler.callback)

    @property
    def states(self):
        return {
            States.ID:
                [MessageHandler(Filters.text, self.handle_id, pass_user_data=True)],
            States.EMAIL:
                [MessageHandler(Filters.text, self.handle_email, pass_user_data=True),
                 CommandHandler(self.DONE_COMMAND, self.handle_email, pass_user_data=True)],
            States.MAIN:
                [CallbackQueryHandler(self.handle_main_state, pass_user_data=True)],
            States.EDIT_ID:
                [MessageHandler(Filters.text, self.handle_edit_id, pass_user_data=True)],
            States.EDIT_EMAIL:
                [MessageHandler(Filters.text, self.handle_edit_email, pass_user_data=True),
                 CommandHandler(self.DONE_COMMAND, self.handle_edit_email, pass_user_data=True)],
            States.HANDLE_ORIGIN_STATION:
                [MessageHandler(Filters.text, self.handle_origin_station, pass_user_data=True)],
            States.HANDLE_DEST_STATION:
                [MessageHandler(Filters.text, self.handle_dest_station, pass_user_data=True)],
            States.HANDLE_TRAIN:
                [MessageHandler(Filters.text, self.handle_train, pass_chat_data=True)],
            States.SAVE_TRAIN:
                [MessageHandler(Filters.text, self.handle_save_train, pass_chat_data=True)],
            States.SAVED_TRAINS:
                [MessageHandler(Filters.text, self.handle_saved_trains, pass_chat_data=True)],
            States.BROADCAST:
                [MessageHandler(Filters.text, self.handle_broadcast, pass_chat_data=True)],
            States.DELETE_SAVED_TRAIN:
                [MessageHandler(Filters.text, self.handle_remove_saved_train, pass_chat_data=True)],
        }

    def _configure_logger(self, logger_level):
        logging.basicConfig(level=logger_level,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        return logger

    def run(self):
        # Create the EventHandler and pass it your bot's token.
        self.updater = Updater(self.token,
                               workers=self.num_threads,
                               use_context=True,
                               persistence=FirebasePersistence(firebase_url=self.firebase_url))

        # Get the dispatcher to register handlers
        dp = self.updater.dispatcher

        # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.handle_start),
                          CommandHandler('broadcast', self.init_broadcast)],
            states=self.states,
            fallbacks=[CommandHandler('stop', self.cancel, pass_user_data=True)],
            allow_reentry=True,
            persistent=True,
            name='main_conversation'
        )

        dp.add_handler(conv_handler)

        # log all errors
        # dp.add_error_handler(error)

        # Start the Bot
        if self.polling:
            self.updater.start_polling()

        else:
            # webhook
            self.updater.start_webhook(listen='0.0.0.0', port=self.port, url_path=self.token)
            self.updater.bot.set_webhook(url=self.host + self.token, max_connections=100)

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        self.logger.info(f"Bot started running, polling={self.polling}, number of threads={self.num_threads}, "
                         f"port={self.port}")
        self.logger.info(f"current timezone is {datetime.datetime.now()}")
        self.updater.idle()

    def _save_user(self, user):
        self.firebase.patch(f'/{self.USERS_KEY}', {str(user.id): user.username})

    @property
    def users(self):
        return self.firebase.get(f"/{self.USERS_KEY}", None)

    @property
    def _next_week(self):
        now = datetime.datetime.now()
        for i in range(7):
            yield now + datetime.timedelta(i)

    def _broadcast_message_to_users(self, message):
        self.logger.info(f"Broadcasting message `{message}`")
        for id, name in self.users.items():
            time.sleep(.1)  # Telegram servers does not let you send more than 30 messages per second
            try:
                self.updater.bot.sendMessage(int(id), message)

            except BaseException as e:
                traceback.print_exc()
                self.logger.debug(f'Failed to broadcast message to {name} due to {e}')

    @property
    def train_stations(self):
        return sorted([train_info['HE'] for train_info in train_api.stations_info.values()])

    @staticmethod
    def _id_valid(id_arg):
        return re.fullmatch(r'\d+', id_arg) is not None

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
                                              keyboard=[[self.BACK]] + keyboard,
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
        id = context.user_data['id']
        email = context.user_data['email']
        email = 'Not supplied' if email == '' else email
        self._reply_message(update,
                            f'ID: {id}\n'
                            f'Email: {email}\n'
                            f'{message}',
                            keyboard=self.MAIN_STATE_OPTIONS,
                            inline_keyboard=True)

    def _replay_coupon(self, context, current_train: train_api.Train, image_path, update):
        self._reply_message(update, str(current_train))
        with open(image_path, 'rb') as f:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(f)

        context.user_data['last_train'] = current_train.to_dict()

    def _is_initiated(self, context):
        user_data = context.user_data
        has_attr = 'id' in user_data and 'email' in user_data
        has_values = self._id_valid(user_data['id'])
        return has_attr and has_values

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

    def _move_to_main_state(self, update, context):
        self._prompt_main_menu(update, context)
        return States.MAIN

    # Handlers
    def init_broadcast(self, update, context):
        if update.message.from_user.id not in self.admins:
            return

        self._reply_message(update, "Please send the message to broadcast")
        return States.BROADCAST

    @run_async
    def handle_broadcast(self, update, context):
        message_to_broadcast = update.message.text
        self._broadcast_message_to_users(message_to_broadcast)
        self._reply_message(update, "done")

        if self._is_initiated(context):
            return self._move_to_main_state(update, context)

        else:
            return self.handle_start(update, context)

    @run_async
    @log_user
    def handle_start(self, update, context):
        self._reply_message(update, self.WELCOME_MESSAGE)
        self._save_user(update.message.from_user)
        self._reply_message(update, 'Please enter your ID')
        return States.ID

    def handle_id(self, update, context):
        user_id = update.message.text
        if not self._id_valid(user_id):
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! ID is {user_id}.\n'
        'Please enter your email address (optional. provide an email address to get order validation and '
        'cancellation link) or send /done.')
        return States.EMAIL

    def handle_email(self, update, context):
        email = update.message.text
        if email == f'/{self.DONE_COMMAND}':  # no email supplied
            email = ''

        elif not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EMAIL

        context.user_data['email'] = email
        return self._move_to_main_state(update, context)

    def handle_main_state(self, update, context):
        option = update.callback_query
        option.answer()

        if option.data == self.EDIT_ID:
            option.edit_message_text(text="Enter new ID")
            return States.EDIT_ID

        if option.data == self.EDIT_EMAIL:
            option.edit_message_text(text='Enter new email address (send /done to skip)')
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
                return self._move_to_main_state(option, context)

            self._reply_message(option,
                                'Choose a train to order from the list below',
                                keyboard=[[i] for i in self._saved_trains(context, printable=True).keys()])
            return States.SAVED_TRAINS

        if option.data == self.REMOVE_SAVED_TRAINS:
            option.edit_message_text(text=self.REMOVE_SAVED_TRAINS)
            if len(self._saved_trains(context)) == 0:
                self._reply_message(option, 'No saved trains found, order first to save')
                return self._move_to_main_state(option, context)

            self._reply_message(option,
                                'Choose a train to delete from the list below',
                                keyboard=[[i] for i in self._saved_trains(context, printable=True).keys()])
            return States.DELETE_SAVED_TRAIN

    def handle_edit_id(self, update, context):
        user_id = update.message.text
        if not self._id_valid(user_id):
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.EDIT_ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! new ID is {user_id}')
        return self._move_to_main_state(update, context)

    def handle_edit_email(self, update, context):
        email = update.message.text
        if email == f'/{self.DONE_COMMAND}':  # no email supplied
            email = ''

        elif not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EDIT_EMAIL

        context.user_data['email'] = email
        self._reply_message(update, f'Success! new email address is {email if email != "" else "empty"}')
        return self._move_to_main_state(update, context)

    @handle_back
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

    @run_async
    @handle_back
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
                    trains = {train.get_printable_travel_time(): train.to_dict() for train in trains}
                    context.user_data['trains'] = trains
                    context.user_data['date'] = day
                    self._reply_train_summary(update, context)
                    return States.HANDLE_TRAIN

            except (ValueError, AttributeError) as e:
                traceback.print_exc()
                self.logger.error(f'exception occurred in get_available_trains {e}')
                self._reply_message(update, 'An error occurred on the server, Please try again')
                return self._move_to_main_state(update, context)

        else:
            self._reply_message(update, "No trains are available for the next week, closing conversation")
            return self._move_to_main_state(update, context)

    @run_async
    @handle_back
    def handle_train(self, update, context):
        train_date = update.message.text
        if train_date not in context.user_data['trains'].keys():
            self._reply_message(update,
                                'Please select a train from the list below',
                                keyboard=[[i] for i in context.user_data['trains'].keys()])
            return States.HANDLE_TRAIN

        current_train = context.user_data['trains'][train_date]
        current_train = train_api.Train.from_json(current_train)

        image_path = 'image.jpeg'
        try:
            self._reply_message(update, "Ordering coupon...")
            train_api.request_train(user_id=context.user_data['id'],
                                    email=context.user_data['email'],
                                    train_json=current_train,
                                    image_dest=image_path)

        except AttributeError as e:
            # error with the arguments passed
            traceback.print_exc()
            self._reply_message(update,
                                'Error occurred in the server, some details might be wrong, please enter them again')
            return self.handle_start(update, context)

        except (ValueError, RuntimeError) as e:
            traceback.print_exc()
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

    @handle_back
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

        return self._move_to_main_state(update, context)

    @handle_back
    def handle_saved_trains(self, update, context):
        selected_train = update.message.text
        saved_trains = self._saved_trains(context, printable=True)
        if selected_train not in saved_trains.keys():
            self._reply_message(update,
                                "Please select a train from the list below",
                                keyboard=[[i] for i in saved_trains.keys()])
            return States.SAVED_TRAINS

        selected_train = train_api.Train.from_json(saved_trains[selected_train])
        user_id = context.user_data['id']
        user_email = context.user_data['email']
        origin_station_id = context.user_data['origin_station_id']
        dest_station_id = context.user_data['dest_station_id']

        now = datetime.datetime.now()
        request_train_datetime = datetime.datetime.combine(now, selected_train.departure_time)
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
            traceback.print_exc()
            self.logger.error(f'exception occurred in get_available_trains {e}')
            self._reply_message(update, 'Error occurred please try again')
            return self._move_to_main_state(update, context)

        for train in available_trains:
            if train.departure_datetime == selected_train.departure_datetime and \
                    train.arrival_datetime == selected_train.arrival_datetime:
                break  # This train exists

        else:  # No trains found
            self._reply_message(update, "The selected train could'nt be found, please check the official site.")
            return self._move_to_main_state(update, context)

        try:
            train_api.request_train(user_id=user_id,
                                    email=user_email,
                                    origin_station_id=origin_station_id,
                                    dest_station_id=dest_station_id,
                                    time_for_request=request_train_datetime,
                                    image_dest='image.jpeg')

            self._replay_coupon(context, selected_train, 'image.jpeg', update)

        except (AttributeError, ValueError, RuntimeError) as e:
            traceback.print_exc()
            self.logger.error(f'exception occurred in request_train {e}')
            self._reply_message(update, 'Error occurred please try again')

        return self._move_to_main_state(update, context)

    @handle_back
    def handle_remove_saved_train(self, update, context):
        selected_train = update.message.text
        saved_trains = self._saved_trains(context, printable=True)
        if selected_train not in saved_trains.keys():
            self._reply_message(update,
                                "Please select a train from the list below",
                                keyboard=[[i] for i in saved_trains.keys()])
            return States.DELETE_SAVED_TRAIN

        selected_train = saved_trains[selected_train]
        context.user_data['saved_trains'].remove(selected_train)
        self._reply_message(update, "Success! train has been removed")
        return self._move_to_main_state(update, context)

    @log_user
    def cancel(self, update, context):
        user = update.message.from_user
        self.logger.info("User %s canceled the conversation.", user.username)
        update.message.reply_text('Goodbye !', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


if __name__ == '__main__':
    if os.path.exists('config.json'):
        with open('config.json', encoding='utf8') as config_file:
            config = json.load(config_file)

    else:
        config = {
            'token': os.environ['TOKEN'],
            'port': os.environ['PORT'],
            'host': os.environ['HOST'],
            'polling': bool(os.environ['POLLING']),
            'num_threads': int(os.environ['NUM_THREADS']),
            "admins": [int(adm.strip()) for adm in os.environ['ADMINS'].split(',')],  # Comma separated ids
            "firebase_url": os.environ['FIREBASE_URL']
        }

    print(config)

    TrainCouponBot(**config).run()
