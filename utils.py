def flatten(deep_list):
    final_list = []
    for item in deep_list:
        if type(item) is list:
            final_list.extend(flatten(item))

        else:
            final_list.append(item)

    return final_list
