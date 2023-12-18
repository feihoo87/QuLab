import numpy as np

style = '''
QWidget {
    font: medium Ubuntu;
    background-color: #011F2F;
    font-size: 16px;
    font-size: 16px;
    color:#FFFFFF;
}
'''
#
Nroll = 6

#  Format of the data.
forms = {
    "mag": lambda w, ang: np.abs(w),
    "phase": lambda w, ang: np.angle(w),
    "real": lambda w, ang: np.real(w),
    "imag": lambda w, ang: np.imag(w),
    "rot": lambda w, ang: np.real(np.exp(1j * ang) * np.array(w))
}
form_keys = list(forms.keys())
#
COL_SEL = (0, 0, 0)
COL_UNSEL = (6, 6, 8)
#

defualt_colors = [
    (200, 0, 0),
    (55, 100, 180),
    (40, 80, 150),
    (30, 50, 110),
    (25, 40, 70),
    (25, 30, 50),
]

widths = [3, 2, 2, 2, 1, 1]
SymSize = [5, 0, 0, 0, 0, 0]
ridx = list(range(Nroll))
ridx.reverse()
