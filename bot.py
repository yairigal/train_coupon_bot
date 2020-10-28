import datetime
import json
import logging
import logging.handlers
import os
import re
import time
import traceback
from functools import wraps
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

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

import train_api
from firebasepersistance import FirebasePersistence
from train_api import Train


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
    """Israel train coupon bot manager.

    Coronavirus times causes bored people to make this.
    Telegram bot that can retrieve a QR image from the train server for a seat in the train.

    Attributes:
        token (str): telegram bot token (secret).
        polling (bool): whether the bot is polling the telegram servers or is on webhook mode (signing for events
            from the telegram servers, this requires the `host` attribute.
        num_threads (number): the amount of threads the bot can open.
        port (number): the port the bot will open and manage connections on.
        firebase_url (str): url of the firebase db to save the state of the bot if the bot goes down.
        admins (list): list of user ids (int) of the admins (can execute admin commands)
        host (str): the name of the host of the bot (relevant for webhook mode).
        logger_level (logging.Level): the logger level.
        log_to_file (bool): whether to save the log into a file on the disk.
        logger_file_amount (number): the maximum amount of files the logs can cycle on (only relevant if log_to_file
            is True).
        logger_file_size (number): the size of each log file (only relevant if log_to_file is True).
    """
    LOG_FILE = 'bot.log'
    USERS_KEY = 'users'

    EDIT_ID = 'Edit ID'
    EDIT_EMAIL = 'Edit Email'
    ORDER_COUPON = 'Order voucher'
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

    def __init__(self,
                 token,
                 polling,
                 num_threads,
                 port,
                 firebase_url,
                 admins=None,
                 host='127.0.0.1',
                 logger_level=logging.INFO,
                 log_to_file=False,
                 logger_file_amount=3,
                 logger_file_size=2 ** 20):
        self.token = token
        self.polling = polling
        self.num_threads = num_threads
        self.host = host
        self.port = port
        self.firebase_url = firebase_url
        if admins is None:
            admins = []

        self.admins = admins
        self.logger = self._configure_logger(logger_level, log_to_file, logger_file_amount, logger_file_size)
        self.firebase = firebase.FirebaseApplication(self.firebase_url)

        # Instead of placing the decorators on each handler, wrap all of them here
        self._wrap_handlers(log_user, move_to_main_on_error)

        # Create the EventHandler and pass it your bot's token.
        self.updater = Updater(self.token,
                               workers=self.num_threads,
                               use_context=True,
                               persistence=FirebasePersistence(firebase_url=self.firebase_url))

        # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.handle_start),
                          CommandHandler('broadcast', self.init_broadcast)],
            states=self.states,
            fallbacks=[CommandHandler('stop', self.cancel, pass_user_data=True)],
            allow_reentry=True,
            persistent=True,
            name='main_conversation'
        )

        self.updater.dispatcher.add_handler(conversation_handler)

    def run(self):
        """Start running the bot in polling / webhook mode."""
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

    @property
    def users(self) -> Dict:
        """Dictionary of users.

        Returns:
            dict. dictionary of id to username (e.g. {'12345':"username"})
        """
        return self.firebase.get(f"/{self.USERS_KEY}", None)

    @property
    def _next_week(self) -> datetime.datetime:
        """Return a generator of the next 7 days from now on in datetime objects."""
        now = datetime.datetime.now()
        for i in range(7):
            yield now + datetime.timedelta(i)

    @property
    def train_stations(self) -> List[str]:
        """return a list of hebrew names of the train stations available."""
        return sorted([train_info['HE'] for train_info in train_api.stations_info.values()])

    @property
    def _stations_keyboard(self):
        return [[i] for i in self.train_stations]

    @staticmethod
    def _id_valid(id_arg):
        return re.fullmatch(r'\d+', id_arg) is not None

    @staticmethod
    def _email_valid(email):
        return re.fullmatch(r'.+@.+', email) is not None

    @staticmethod
    def _trains_keyboard(context):
        return [[i] for i in context.user_data['trains'].keys()]

    @staticmethod
    def _saved_trains(context):
        if 'saved_trains' not in context.user_data:
            context.user_data['saved_trains'] = {}

        return context.user_data['saved_trains']

    def _wrap_handlers(self, *wrappers):
        """Decorate each state handler.

        Args:
            *wrappers (func): decorator function to wrap the state handler with.
"       """
        for state, handler_list in self.states.items():
            for handler in handler_list:
                for wrapper in wrappers:
                    handler.callback = wrapper(handler.callback)

    def _configure_logger(self, logger_level, log_to_file, logger_file_amount, logger_file_size):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logger_level)

        ch = logging.StreamHandler()
        ch.setLevel(logger_level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        logger.addHandler(ch)

        if log_to_file:
            fh = logging.handlers.RotatingFileHandler('train_bot.log',
                                                      maxBytes=logger_file_size,
                                                      backupCount=logger_file_amount)
            fh.setLevel(logger_level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        return logger

    def _save_user(self, user):
        """Save a user's name and id to firebase DB for sending messages later.

        Args:
            user (telegram.user.User): the user to save to db.
        """
        self.firebase.patch(f'/{self.USERS_KEY}', {str(user.id): user.username})

    def _broadcast_message_to_users(self, message):
        """Send a message to all active users.

        Args:
            message (str): message to send.

        Note:
            There is a delay between messages because telegram servers do not allow more than 20/30 messages per second.
        """
        self.logger.info(f"Broadcasting message `{message}`")
        for id, name in self.users.items():
            time.sleep(.1)  # Telegram servers does not let you send more than 30 messages per second
            try:
                self.updater.bot.sendMessage(int(id), message)

            except BaseException as e:
                traceback.print_exc()
                self.logger.debug(f'Failed to broadcast message to {name} due to {e}')

    def _reformat_to_readable_date(self, d: datetime.datetime) -> str:
        """Convert datetime object into readable date label.

        Args:
            d (datetime.datetime): the datetime object.

        Returns:
            str. formatted datetime (e.g. 'Sun Oct  4').
        """
        return re.fullmatch("(.*) \d+:.*", d.ctime()).group(1)

    def _reply_message(self, update, message, keyboard: List[List[str]] = None, inline_keyboard=False):
        """Return a message to the user.

        Args:
            update (telegram.update.Update): handler update.
            message (str): the message to reply.
            keyboard (List): Optional. list of list of string representing the keyboard to reply to the user
            inline_keyboard (bool): Optional. whether to return a Replymarkup keyboard or inline keyboard.
        """
        if keyboard is not None:
            if not inline_keyboard:
                update.message.reply_text(message,
                                          reply_markup=ReplyKeyboardMarkup(
                                              keyboard=[[self.BACK]] + keyboard,
                                              one_time_keyboard=True))

            else:
                kybd = [[InlineKeyboardButton(lb, callback_data=lb) for lb in lst] for lst in keyboard]
                kybd = InlineKeyboardMarkup(inline_keyboard=kybd)
                update.message.reply_text(message, reply_markup=kybd)

        else:
            update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())

    def _reply_trains_list(self, update, context, date):
        """Send the list of trains to the user.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
        """
        origin_station = train_api.train_station_id_to_name(context.user_data['origin_station_id'])
        dest_station = train_api.train_station_id_to_name(context.user_data['dest_station_id'])
        selected_date = self._reformat_to_readable_date(date)
        self._reply_message(update,
                            f'Displaying trains for\n'
                            f'{origin_station} -> {dest_station}\n'
                            f'on {selected_date}',
                            keyboard=self._trains_keyboard(context))

    def _prompt_main_menu(self, update, context, message='Please choose an option:'):
        """Send the user the main state options in inline keyboard.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
            message (str): Optional. the message to prompt with the keyboard.
        """
        id = context.user_data['id']
        email = context.user_data['email']
        email = 'Not supplied' if email == '' else email
        self._reply_message(update,
                            f'ID: {id}\n'
                            f'Email: {email}\n'
                            f'{message}',
                            keyboard=self.MAIN_STATE_OPTIONS,
                            inline_keyboard=True)

    def _replay_coupon(self, update, context, current_train: Train, image_path):
        """Send the user train description and the QR image.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
            current_train (train_api.Train): the train to order.
            image_path (str): path to the qr image file.
        """
        self._reply_message(update, str(current_train))
        with open(image_path, 'rb') as qr_image:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(qr_image)

        context.user_data['last_train'] = current_train.to_dict()

    def _is_initiated(self, context):
        """Tell whether the current user has id and email already saved.

        Args:
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            bool. whether the user has a correct id and an email.
        """
        user_data = context.user_data
        has_attr = 'id' in user_data and 'email' in user_data
        has_values = self._id_valid(user_data['id'])
        return has_attr and has_values

    def _saved_trains_keyboard(self, context):
        return [[i] for i in self._saved_trains(context).keys()]

    def _move_to_main_state(self, update, context):
        self._prompt_main_menu(update, context)
        return States.MAIN

    def _handle_train_order(self,
                            update,
                            context,
                            request_train_datetime,
                            selected_train):
        """Order train and send the QR image.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
            request_train_datetime (datetime.datetime): the date and time of the train.
            selected_train (Train): the selected train by the user.
        """
        try:
            self._reply_message(update,
                                message="Ordering coupon...")
            image_path = f"{time.time_ns()}.jpeg"
            train_api.request_train(user_id=context.user_data['id'],
                                    email=context.user_data['email'],
                                    origin_station_id=context.user_data['origin_station_id'],
                                    dest_station_id=context.user_data['dest_station_id'],
                                    time_for_request=request_train_datetime,
                                    image_dest=image_path)
            self._replay_coupon(update, context, selected_train, image_path)
            os.remove(image_path)

        except (AttributeError, ValueError, RuntimeError) as e:
            traceback.print_exc()
            self.logger.error(f'exception occurred in request_train {e}')
            self._reply_message(update, 'Error occurred please try again')

    def _save_train(self, context):
        """Save the last train into the saved_trains dict.

        Args:
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
        """
        last_train = context.user_data['last_train']
        saved_trains: dict = self._saved_trains(context)
        if last_train not in saved_trains.values():
            train_label = Train.from_json(last_train).one_line_description()
            saved_trains[train_label] = last_train

        # free memory
        context.user_data['last_train'] = {}

    def _validate_train_exists(self,
                               selected_train,
                               origin_station_id,
                               dest_station_id,
                               request_train_datetime) -> Train:
        """Check that the selected train is available in the train servers.

        Args:
            selected_train (Train): the train the user selected.
            origin_station_id (number): original station id.
            dest_station_id (number): destination station id.
            request_train_datetime (datetime.datetime): the date and time of the train.

        Returns:
            Train. return the train if found one the servers or None is no train found.
        """
        available_trains = train_api.get_available_trains(origin_station_id,
                                                          dest_station_id,
                                                          date=request_train_datetime)

        for train in available_trains:
            if train.departure_datetime == selected_train.departure_datetime and \
                    train.arrival_datetime == selected_train.arrival_datetime:
                return train

    def _handle_train_validation(self,
                                 update,
                                 context,
                                 selected_train,
                                 request_train_datetime) -> Union[Train, int]:
        """Validates train exists and handle all sort of exceptions.

        Checking that the train exists in that specific datetime.
        if not, returning back to the main state.
        also if an exception is thrown from the api, returning to main state.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.
            selected_train (Train): the user selected train to validate.
            request_train_datetime (datetime.datetime): the date and time of the train.

        Returns:
            Train / int. Train object is returned if train was found. if an error occured, the next state is returned.
        """
        try:
            train = self._validate_train_exists(selected_train,
                                                context.user_data['origin_station_id'],
                                                context.user_data['dest_station_id'],
                                                request_train_datetime)
            if train is None:
                self._reply_message(update, "The selected train could'nt be found, please check the official site.")
                return self._move_to_main_state(update, context)

            return train

        except (AttributeError, ValueError) as e:
            traceback.print_exc()
            self.logger.error(f'exception occurred in get_available_trains {e}')
            self._reply_message(update, 'Error occurred please try again')
            return self._move_to_main_state(update, context)

    def _get_next_available_train_list(self, context) -> Tuple[List, datetime.datetime]:
        """Return the first day which has trains available.

        Search the next week from now if there are trains available.

        Args:
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            tuple. the list of trains and the day that the trains are available.

        Raises:
            RuntimeError: general error happened on the server.
        """
        try:
            for day in self._next_week:
                trains = list(train_api.get_available_trains(origin_station_id=context.user_data['origin_station_id'],
                                                             dest_station_id=context.user_data['dest_station_id'],
                                                             date=day))
                if len(trains) > 0:
                    return trains, day

        except (ValueError, AttributeError):
            traceback.print_exc()
            raise RuntimeError("general error")

    # State handlers
    @move_to_main_on_error
    @log_user
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
        user_id = update.message.text.strip()
        if not self._id_valid(user_id):
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! ID is {user_id}.\n'
        'Please enter your email address (optional. provide an email address to get order validation and '
        'cancellation link) or send /done.')
        return States.EMAIL

    def handle_email(self, update, context):
        email = update.message.text.strip()
        if email == f'/{self.DONE_COMMAND}':  # no email supplied
            email = ''

        elif not self._email_valid(email):
            self._reply_message(update, 'email is not valid, please enter valid email address')
            return States.EMAIL

        context.user_data['email'] = email
        return self._move_to_main_state(update, context)

    def handle_main_state(self, update, context):
        """Main state callback.

        The main state has an options to branch to multiple states via inline keyboard:
            * edit id
            * edit email
            * order coupon
            * saved trains
            * remove saved train

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            number. the new state to move to.
        """
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
            self._reply_message(option,
                                message='Please choose an origin station from the list below',
                                keyboard=self._stations_keyboard)
            return States.HANDLE_ORIGIN_STATION

        if option.data == self.SAVED_TRAINS:
            option.edit_message_text(text=self.SAVED_TRAINS)
            if len(self._saved_trains(context)) == 0:
                self._reply_message(option, 'No saved trains found, order first to save')
                return self._move_to_main_state(option, context)

            self._reply_message(option,
                                message='Choose a train to order from the list below',
                                keyboard=self._saved_trains_keyboard(context))
            return States.SAVED_TRAINS

        if option.data == self.REMOVE_SAVED_TRAINS:
            option.edit_message_text(text=self.REMOVE_SAVED_TRAINS)
            if len(self._saved_trains(context)) == 0:
                self._reply_message(option, "You don't have saved trains")
                return self._move_to_main_state(option, context)

            self._reply_message(option,
                                message='Choose a train to delete from the list below',
                                keyboard=self._saved_trains_keyboard(context))
            return States.DELETE_SAVED_TRAIN

    def handle_edit_id(self, update, context):
        user_id = update.message.text.strip()
        if not self._id_valid(user_id):
            self._reply_message(update, 'ID is not valid, please enter valid ID')
            return States.EDIT_ID

        context.user_data['id'] = user_id
        self._reply_message(update, f'Success! new ID is {user_id}')
        return self._move_to_main_state(update, context)

    def handle_edit_email(self, update, context):
        email = update.message.text.strip()
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
                                message='Please choose a station from the list below',
                                keyboard=self._stations_keyboard)
            return States.HANDLE_ORIGIN_STATION

        context.user_data['origin_station_id'] = train_api.train_station_name_to_id(origin_station)
        self._reply_message(update,
                            f'Success! origin station picked is {origin_station}.\n'
                            f'Please choose a destination station from the list below',
                            keyboard=self._stations_keyboard)
        return States.HANDLE_DEST_STATION

    @run_async
    @handle_back
    def handle_dest_station(self, update, context):
        destination_station = update.message.text
        if destination_station not in self.train_stations:
            self._reply_message(update,
                                message='Please choose a station from the list below',
                                keyboard=self._stations_keyboard)
            return States.HANDLE_DEST_STATION

        context.user_data['dest_station_id'] = train_api.train_station_name_to_id(destination_station)

        try:
            self._reply_message(update, message="retrieving trains...")
            trains = self._get_next_available_train_list(context)
            if trains is None:
                self._reply_message(update, "No trains are available for the next week")
                return self._move_to_main_state(update, context)

            trains, day = trains
            trains = {train.get_printable_travel_time(): train.to_dict() for train in trains}
            context.user_data['trains'] = trains
            self._reply_trains_list(update, context, date=day)
            return States.HANDLE_TRAIN

        except RuntimeError:
            self._reply_message(update, 'An error occurred on the server, Please try again')
            return self._move_to_main_state(update, context)

    @run_async
    @handle_back
    def handle_train(self, update, context):
        train_date = update.message.text
        if train_date not in context.user_data['trains'].keys():
            self._reply_message(update,
                                message='Please select a train from the list below',
                                keyboard=self._trains_keyboard(context))
            return States.HANDLE_TRAIN

        current_train = context.user_data['trains'][train_date]
        current_train: Train = Train.from_json(current_train)

        try:
            self._reply_message(update, "Ordering coupon...")
            image_path = f"{time.time_ns()}.jpeg"
            train_api.request_train(user_id=context.user_data['id'],
                                    email=context.user_data['email'],
                                    train_instance=current_train,
                                    image_dest=image_path)
            self._replay_coupon(update, context, current_train, image_path)
            os.remove(image_path)
            self._reply_message(update,
                                "Save this train for faster access?",
                                keyboard=[['Yes', 'No']])
            # free unnecessary memory
            context.user_data['trains'] = {}
            return States.SAVE_TRAIN

        except AttributeError:
            # error with the arguments passed
            traceback.print_exc()
            self._reply_message(update,
                                message='Error occurred in the server, some details might be wrong, '
                                        'please enter them again')
            return self.handle_start(update, context)

        except (ValueError, RuntimeError):
            traceback.print_exc()
            self._reply_message(update,
                                'No barcode image received from the server. This might happen if the same seat is '
                                'ordered twice. Please pick another seat')
            self._reply_trains_list(update, context, date=current_train.departure_datetime)
            return States.HANDLE_TRAIN

    @handle_back
    def handle_save_train(self, update, context):
        option = update.message.text.lower()
        if option not in ['yes', 'no']:
            self._reply_message(update,
                                'Please reply yes or no',
                                keyboard=[['Yes', 'No']])
            return States.SAVE_TRAIN

        if option == 'yes':
            self._save_train(context)
            self._reply_message(update, 'Success! train added to saved trains')

        return self._move_to_main_state(update, context)

    @run_async
    @handle_back
    def handle_saved_trains(self, update, context):
        """Saved trains state callback.

        This state does multiple actions:
        * input validation, validate the train input is one of the saved trains.
        * Verify the time of the train has not passed.
        * Validate the train is available.
        * order the train.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            int. the new state to move to.
        """
        selected_train_label = update.message.text
        saved_trains = self._saved_trains(context)
        selected_train = Train.from_json(saved_trains[selected_train_label])
        if selected_train_label not in saved_trains.keys():
            self._reply_message(update,
                                message="Please select a train from the list below",
                                keyboard=self._saved_trains_keyboard(context))
            return States.SAVED_TRAINS

        # Construct train datetime object
        now = datetime.datetime.now()
        # request date = the current date + train time
        request_train_datetime = datetime.datetime.combine(now, selected_train.departure_datetime.time())
        if now > request_train_datetime:
            self._reply_message(update,
                                message='Train departure time has passed',
                                keyboard=self._saved_trains_keyboard(context))
            return States.SAVED_TRAINS

        # Validate train exists.
        train = self._handle_train_validation(update,
                                              context,
                                              selected_train,
                                              request_train_datetime)
        if isinstance(train, int):  # Error occurred, returning new state.
            return train

        # Order train
        self._handle_train_order(update,
                                 context,
                                 request_train_datetime,
                                 selected_train)

        return self._move_to_main_state(update, context)

    @handle_back
    def handle_remove_saved_train(self, update, context):
        """Remove saved train state callback.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            int. the new state to move to.
        """
        selected_train_label = update.message.text
        saved_trains = self._saved_trains(context)
        if selected_train_label not in saved_trains.keys():
            self._reply_message(update,
                                "Please select a train from the list below",
                                keyboard=self._saved_trains_keyboard(context))
            return States.DELETE_SAVED_TRAIN

        context.user_data['saved_trains'].pop(selected_train_label)
        self._reply_message(update, "Success! train has been removed")
        return self._move_to_main_state(update, context)

    @log_user
    def cancel(self, update, context):
        """Stop command fallback callback.

        Args:
            update (telegram.update.Update): current telegram update.
            context (telegram.ext.callbackcontext.CallbackContext): current chat context.

        Returns:
            int. end conversation state.
        """
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
