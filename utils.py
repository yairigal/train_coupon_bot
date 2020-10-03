import json


def flatten(deep_list):
    final_list = []
    for item in deep_list:
        if type(item) is list:
            final_list.extend(flatten(item))

        else:
            final_list.append(item)

    return final_list


def enocde_conversations(conversations):
    """Helper method to encode a conversations dict (that uses tuples as keys) to a
    JSON-serializable way. Use :attr:`_decode_conversations_from_json` to decode.

    Args:
        conversations (:obj:`dict`): The conversations dict to transofrm to JSON.

    Returns:
        :obj:`dict`: The JSON-serialized conversations dict
    """
    tmp = {}
    for handler, states in conversations.items():
        tmp[handler] = {}
        for key, state in states.items():
            key_in_list_format = json.dumps(key)
            # Converting to tuple format since firebase cannot handle [ and ]
            key_in_tuple_format = key_in_list_format.replace("[", "(").replace("]", ")")
            tmp[handler][key_in_tuple_format] = state
    return tmp


def decode_conversations(conversations_dict):
    """Helper method to decode a conversations dict (that uses tuples as keys) from a
    JSON-string created with :attr:`_encode_conversations_to_json`.

    Args:
        json_string (:obj:`str`): The conversations dict as JSON string.

    Returns:
        :obj:`dict`: The conversations dict after decoding
    """
    tmp = conversations_dict
    conversations = {}
    for handler, states in tmp.items():
        conversations[handler] = {}
        for key, state in states.items():
            json_in_list_format = key.replace("(", "[").replace(")", "]")
            key_in_list_format = json.loads(json_in_list_format)
            key_in_tuple_format = tuple(key_in_list_format)
            conversations[handler][key_in_tuple_format] = state
    return conversations