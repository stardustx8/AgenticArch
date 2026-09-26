import unicodedata
def canonical_key(text):
    s=unicodedata.normalize("NFC",text).casefold()
    return " ".join(unicodedata.normalize("NFC",s).split())
