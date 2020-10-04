import copy
import json
from collections import defaultdict

from cached_property import cached_property
from firebase import firebase
from telegram.ext import BasePersistence
from telegram.utils.helpers import decode_user_chat_data_from_json
from telegram.utils.promise import Promise

from utils import decode_conversations
from utils import enocde_conversations


# TODO add authentication
class FirebasePersistence(BasePersistence):
    USER_DATA_KEY = 'user_data'
    CHAT_DATA_KEY = 'chat_data'
    CONVERSATION_KEY = 'conversations'

    def __init__(self, firebase_url):
        super().__init__()
        self.firebase = firebase.FirebaseApplication(firebase_url)

    @cached_property
    def user_data(self):
        user_data = self.firebase.get(f'/{self.USER_DATA_KEY}', None)
        if user_data is None:
            user_data = {}

        user_data = decode_user_chat_data_from_json(json.dumps(user_data))
        return defaultdict(dict, user_data)

    @cached_property
    def chat_data(self):
        chat_data = self.firebase.get(f'/{self.CHAT_DATA_KEY}', None)
        if chat_data is None:
            chat_data = {}

        chat_data = decode_user_chat_data_from_json(json.dumps(chat_data))
        return defaultdict(dict, chat_data)

    @cached_property
    def conversations(self):
        conversation = self.firebase.get(f'/{self.CONVERSATION_KEY}', None)
        if conversation is None:
            conversation = {}

        return decode_conversations(conversation)

    def _save_user_data(self):
        self.firebase.put('/', self.USER_DATA_KEY, self.user_data)

    def _save_chat_data(self):
        self.firebase.put('/', self.CHAT_DATA_KEY, self.chat_data)

    def _save_conversations(self):
        # need the helper function because the keys are tuples and cannot be encoded to json
        json_conversations = enocde_conversations(self.conversations)
        self.firebase.put('/', self.CONVERSATION_KEY, json_conversations)

    def get_chat_data(self):
        return copy.deepcopy(self.chat_data)

    def get_user_data(self):
        return copy.deepcopy(self.user_data)

    def get_conversations(self, name):
        return copy.deepcopy(self.conversations.get(name, {}))

    def update_conversation(self, name, key, new_state):
        if name not in self.conversations:
            self.conversations[name] = {}

        # need this patch in case the result is running async (promise) since there is no support for this from
        # python-telegram-bot
        if isinstance(new_state, tuple):
            old_state, new_state = new_state
            if isinstance(new_state, Promise):
                new_state = new_state.result()

        self.conversations[name][key] = new_state

    def update_user_data(self, user_id, data):
        self.user_data[user_id] = data

    def update_chat_data(self, chat_id, data):
        self.chat_data[chat_id] = data

    def flush(self):
        self._save_chat_data()
        self._save_user_data()
        self._save_conversations()
