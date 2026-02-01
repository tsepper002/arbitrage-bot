import time


def is_book_alive(book, max_age):
    if not book:
        return False

    ts = book.get("ts")
    if not ts:
        return False

    return (time.time() - ts) <= max_age
