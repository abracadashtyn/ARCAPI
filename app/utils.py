import unicodedata

def remove_accent_marks(text):
    nfd = unicodedata.normalize('NFD', text)
    return ''.join([x for x in nfd if unicodedata.category(x) != 'Mn'])


def format_name_to_image_file(name):
    name = remove_accent_marks(name)
    return name.replace(" ", "").lower() + '.png'