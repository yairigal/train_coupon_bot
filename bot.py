import os
import json
import logging
import datetime
from abc import ABCMeta, abstractmethod
from functools import wraps

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
                States.HANDLE_DATE: [MessageHandler(Filters.text, self.handle_date, pass_user_data=True)],
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
        self.updater.idle()

    def _save_user(self, user):
        if not os.path.exists(self.USERS_FILE):
            # Create an empty json file
            with open(self.USERS_FILE, "w") as cts:
                cts.write("{}")

        with open(self.USERS_FILE) as cts:
            contacts = json.load(cts)

        contacts[str(user.id)] = f"{user.first_name} {user.last_name}"

        with open(self.USERS_FILE, "w") as cts:
            json.dump(contacts, cts)

    def _get_next_week(self):
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
                self.logger.debug(f'Failed to broadcase message to {name} due to {e}')

    @property
    def train_stations(self):
        return train_api.id_to_station.values()

    # Handlers
    @log_user
    def handle_start(self, update, context):
        self._save_user(update.message.from_user)
        update.message.reply_text('Please enter your ID', reply_markup=ReplyKeyboardRemove())
        return States.ID

    @log_user
    def handle_id(self, update, context):
        context.user_data['id'] = update.message.text
        update.message.reply_text('Please enter your phone number', reply_markup=ReplyKeyboardRemove())
        return States.PHONE

    @log_user
    def handle_phone(self, update, context):
        context.user_data['phone'] = update.message.text
        update.message.reply_text('Please enter your email address', reply_markup=ReplyKeyboardRemove())
        return States.EMAIL

    @log_user
    def handle_email(self, update, context):
        context.user_data['email'] = update.message.text
        update.message.reply_text('Got all data! choose origin station',
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=[[i] for i in self.train_stations],
                                      one_time_keyboard=True))
        return States.HANDLE_ORIGIN_STATION

    @log_user
    def handle_origin_station(self, update, context):
        context.user_data['origin_station'] = update.message.text
        update.message.reply_text('Choose destination',
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=[[i] for i in self.train_stations],
                                      one_time_keyboard=True))
        return States.HANDLE_DEST_STATION

    @log_user
    def handle_dest_station(self, update, context):
        context.user_data['dest_station'] = update.message.text
        week_datetimes = self._get_next_week()
        labels_to_dates = {}
        labels_to_dates['Today'] = next(week_datetimes)
        labels_to_dates['Tomorrow'] = next(week_datetimes)
        labels_to_dates.update({date.strftime('%d/%m/%Y'): date for date in week_datetimes})
        context.user_data['dates'] = labels_to_dates

        update.message.reply_text('Choose a day',
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=[[i] for i in labels_to_dates.keys()],
                                      one_time_keyboard=True))
        return States.HANDLE_DATE

    @log_user
    def handle_date(self, update, context):
        date = context.user_data['dates'][update.message.text]
        origin_station_id = train_api.train_station_name_to_id(context.user_data['origin_station'])
        dest_station_id = train_api.train_station_name_to_id(context.user_data['dest_station'])

        res = train_api.get_available_trains(origin_station_id=origin_station_id,
                                             dest_station_id=dest_station_id,
                                             date=date)

        trains = {f"{train['DepartureTime']} - {train['ArrivalTime']}": train for train in res}
        if len(trains) == 0:
            update.message.reply_text(f'No trains available for {date}, Please pick a new date',
                                      reply_markup=ReplyKeyboardMarkup(
                                          keyboard=[[i] for i in context.user_data['dates'].keys()],
                                          one_time_keyboard=True))
            return States.HANDLE_DATE

        context.user_data['trains'] = trains
        update.message.reply_text('Pick a train',
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=[[i] for i in trains.keys()],
                                      one_time_keyboard=True))
        return States.HANDLE_TRAIN

    @log_user
    def handle_train(self, update, context):
        train_date = update.message.text
        current_train = context.user_data['trains'][train_date]
        train_api.request_train(user_id=context.user_data['id'],
                                mobile=context.user_data['phone'],
                                email=context.user_data['email'],
                                train_json=current_train,
                                image_dest='image.jpeg')

        with open('image.jpeg', 'rb') as f:
            update.message.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                                action=ChatAction.UPLOAD_PHOTO)
            update.message.reply_photo(f)

        update.message.reply_text('Order another coupon?',
                                  reply_markup=ReplyKeyboardMarkup(
                                      keyboard=[['Order Different Train'], ['Order the same', 'Close']],
                                      one_time_keyboard=True))

        return States.WHETHER_TO_CONTINUE

    @log_user
    def handle_whether_to_continue(self, update, context):
        answer = update.message.text
        if answer == 'Order Different Train':
            update.message.reply_text('Choose origin station',
                                      reply_markup=ReplyKeyboardMarkup(
                                          keyboard=[[i] for i in train_api.id_to_station.values()],
                                          one_time_keyboard=True))
            return States.HANDLE_ORIGIN_STATION

        elif answer == 'Order the same':
            update.message.reply_text('Choose time',
                                      reply_markup=ReplyKeyboardMarkup(
                                          keyboard=[[i] for i in context.user_data['dates'].keys()],
                                          one_time_keyboard=True))
            return States.HANDLE_DATE

        else:
            return ConversationHandler.END

    @log_user
    def cancel(self, update, context):
        user = update.message.from_user
        self.logger.info("User %s canceled the conversation.", user.first_name)
        update.message.reply_text('Goodbye !', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


if __name__ == '__main__':
    with open('config.json', encoding='utf8') as config_file:
        config = json.load(config_file)

    # Read token
    with open("token") as token:
        TOKEN = token.read().strip('\n')

    TrainCouponBot(token=TOKEN, **config).run()
