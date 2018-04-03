import quantities as pq

def unit(name):
    return getattr(pq, name)
    