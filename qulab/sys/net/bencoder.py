"""
This module provides a simple bencoding implementation in pure Python.
Bencoding is a way to specify and organize data in a terse format. It supports
the following types: byte strings, integers, lists, and dictionaries.

Classes:
    Bencached: A class that holds bencoded data.

Functions:
    encode_bencached(x, fp): Encodes a Bencached object.
    encode_int(x, fp): Encodes an integer.
    encode_bool(x, fp): Encodes a boolean.
    encode_string(x, fp): Encodes a string.
    encode_list(x, fp): Encodes a list.
    encode_dict(x, fp): Encodes a dictionary.
    decode_int(x, ptr): Decodes a bencoded integer.
    decode_string(x, ptr): Decodes a bencoded string.
    decode_list(x, ptr): Decodes a bencoded list.
    decode_dict(x, ptr): Decodes a bencoded dictionary.
    encode(obj, fp): Encodes an object.
    encodes(obj): Encodes an object and returns the bencoded bytes.
    decode(fp): Decodes a file-like object.
    decodes(s): Decodes a bencoded bytes object.
    dump = encode: Alias for encode function.
    load = decodes: Alias for decode function.
    dumps = encodes: Alias for encodes function.
    loads = decodes: Alias for decodes function.

Examples:
    >>> encode(42) == b'i42e'
    True
    >>> decode(b'i42e')
    42
"""
import io


class Bencached():

    __slots__ = ['bencoded']

    def __init__(self, s):
        self.bencoded = s


def encode_bencached(x, fp):
    fp.write(x.bencoded)


def encode_int(x, fp):
    fp.write(f"i{x}e".encode())


def encode_bool(x, fp):
    if x:
        encode_int(1, fp)
    else:
        encode_int(0, fp)


def encode_string(x, fp):
    if isinstance(x, str):
        x = x.encode()
    fp.write(f"{len(x):d}:".encode())
    fp.write(x)


def encode_list(x, fp):
    fp.write(b'l')
    for i in x:
        encode_func[type(i)](i, fp)
    fp.write(b'e')


def encode_dict(x, fp):
    fp.write(b'd')
    for k, v in sorted(x.items()):
        if isinstance(k, str):
            k = k.encode()
        fp.write(f"{len(k):d}:".encode())
        fp.write(k)
        encode_func[type(v)](v, fp)
    fp.write(b'e')


encode_func = {
    Bencached: encode_bencached,
    int: encode_int,
    str: encode_string,
    bytes: encode_string,
    list: encode_list,
    tuple: encode_list,
    dict: encode_dict,
    bool: encode_bool
}


def decode_int(x, ptr):
    ptr += 1
    end = x.index(b'e', ptr)
    if x[ptr] == b'-'[0]:
        if x[ptr + 1] == b'0'[0]:
            raise ValueError
    elif x[ptr] == b'0'[0] and end != ptr + 1:
        raise ValueError
    n = int(x[ptr:end])
    return n, end + 1


def decode_string(x, ptr):
    colon = x.index(b':', ptr)
    n = int(x[ptr:colon])
    if x[ptr] == b'0'[0] and colon != ptr + 1:
        raise ValueError
    colon += 1
    return x[colon:colon + n], colon + n


def decode_list(x, ptr):
    r, ptr = [], ptr + 1
    while x[ptr] != b'e'[0]:
        v, ptr = decode_func[x[ptr]](x, ptr)
        r.append(v)
    return r, ptr + 1


def decode_dict(x, ptr):
    r, ptr = {}, ptr + 1
    while x[ptr] != b'e'[0]:
        k, ptr = decode_string(x, ptr)
        if isinstance(k, bytes):
            k = k.decode()
        r[k], ptr = decode_func[x[ptr]](x, ptr)
    return r, ptr + 1


decode_func = {b'l'[0]: decode_list, b'd'[0]: decode_dict, b'i'[0]: decode_int}

for i in range(10):
    decode_func[f"{i}".encode()[0]] = decode_string


def encode(obj, fp):
    try:
        encode_func[type(obj)](obj, fp)
    except KeyError:
        raise ValueError("Allowed types: int, bytes, list, dict; not %s",
                         type(obj))


def encodes(obj):
    """
    bencodes given object. Given object should be a int,
    bytes, list or dict. If a str is given, it'll be
    encoded as ASCII.
    >>> [encode(i) for i in (-2, 42, b"answer", b"")] \
            == [b'i-2e', b'i42e', b'6:answer', b'0:']
    True
    >>> encode([b'a', 42, [13, 14]]) == b'l1:ai42eli13ei14eee'
    True
    >>> encode({'bar': b'spam', 'foo': 42, 'mess': [1, b'c']}) \
            == b'd3:bar4:spam3:fooi42e4:messli1e1:cee'
    True
    """
    buff = io.BytesIO()
    encode(obj, buff)
    return buff.getvalue()


def decodes(s):
    """
    Decodes given bencoded bytes object.
    >>> decode(b'i-42e')
    -42
    >>> decode(b'4:utku') == b'utku'
    True
    >>> decode(b'li1eli2eli3eeee')
    [1, [2, [3]]]
    >>> decode(b'd3:bar4:spam3:fooi42ee') == {'bar': b'spam', 'foo': 42}
    True
    """
    if isinstance(s, str):
        s = s.encode()
    try:
        r, l = decode_func[s[0]](s, 0)
    except (IndexError, KeyError, ValueError):
        raise ValueError("not a valid bencoded string")
    if l != len(s):
        raise ValueError("invalid bencoded value (data after valid prefix)")
    return r


def decode(fp):
    """
    Decodes given file-like object.
    """
    return decodes(fp.read())


dump = encode
load = decodes
dumps = encodes
loads = decodes

__all__ = ['decodes', 'encodes', 'dump', 'load', 'dumps', 'loads']
