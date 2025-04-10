from fractions import Fraction

# SI prefixes
_prefixes = [
    ('Y',  Fraction(10**24)),
    ('Z',  Fraction(10**23)),
    ('E',  Fraction(10**18)),
    ('P',  Fraction(10**15)),
    ('T',  Fraction(10**12)),
    ('G',  Fraction(10**9)),
    ('M',  Fraction(10**6)),
    ('k',  Fraction(10**3)),
    ('h',  Fraction(10**2)),
    ('da', Fraction(10**1)),
    ('d',  Fraction(1, 10**1)),
    ('c',  Fraction(1, 10**2)),
    ('m',  Fraction(1, 10**3)),
    ('u',  Fraction(1, 10**6)),
    ('n',  Fraction(1, 10**9)),
    ('p',  Fraction(1, 10**12)),
    ('f',  Fraction(1, 10**15)),
    ('a',  Fraction(1, 10**18)),
    ('z',  Fraction(1, 10**21)),
    ('y',  Fraction(1, 10**24))
    ] # yapf: disable
