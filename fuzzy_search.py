from fuzzywuzzy import process
from medical_words import medical_words

def find_medical_term(query, limit=5):
    """
    Finds the best medical term matches for a given query.
    """
    return [match[0] for match in process.extract(query, medical_words, limit=limit)]
