subscribers = []

def subscribe(callback):
    subscribers.append(callback)

def log(message):
    print(message)

    for callback in subscribers:
        callback(message)