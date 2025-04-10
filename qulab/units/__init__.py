import numpy as np


def get_unit_prefix(value):
    '''
    获取 value 合适的单位前缀，以及相应的倍数

    Returns:
        (prefix, multiple)
    '''
    prefixs = [
        'y', 'z', 'a', 'f', 'p', 'n', 'u', 'm', '', 'k', 'M', 'G', 'T', 'P',
        'E', 'Z', 'Y'
    ]
    if value == 0:
        return '', 1
    x = np.floor(np.log10(abs(value)) / 3)
    x = 0 if x < -8 else x
    x = 0 if x > 8 else x
    return prefixs[int(x) + 8], 1000**(x)


def valueString(value, unit=""):
    """
    将 value 转换为更易读的形式

    >>> valueString(1.243e-7, 's')
    ... "124.3 ns"
    >>> valueString(1.243e10, 'Hz')
    ... "12.43 GHz"
    """
    prefix, k = get_unit_prefix(value)
    return f"{value/k:g} {prefix}{unit}"


def dBm2Vpp(x, R0=50):
    """
    Convert dBm to Vpp

    Parameters
    ----------
    x : float
        Power in dBm
    R0 : float
        Load resistance in Ohms

    Returns
    -------
    Vpp : float
        Peak-to-peak voltage in Volts
    """
    mP = 10**(x / 10)
    Vrms = np.sqrt(mP * 1e-3 * R0)
    Vpp = 2 * Vrms * np.sqrt(2)
    return Vpp


def Vpp2dBm(x, R0=50):
    """
    Convert Vpp to dBm

    Parameters
    ----------
    x : float
        Peak-to-peak voltage in Volts
    R0 : float
        Load resistance in Ohms

    Returns
    -------
    dBm : float
        Power in dBm
    """
    Vrms = x / np.sqrt(2) / 2
    mP = Vrms**2 / R0 * 1e3
    dBm = 10 * np.log10(mP)
    return dBm


def dBm2Vrms(x, R0=50):
    """
    Convert dBm to Vrms

    Parameters
    ----------
    x : float
        Power in dBm
    R0 : float
        Load resistance in Ohms

    Returns
    -------
    Vrms : float
        RMS voltage in Volts
    """
    mP = 10**(x / 10)
    Vrms = np.sqrt(mP * 1e-3 * R0)
    return Vrms


def Vrms2dBm(x, R0=50):
    """
    Convert Vrms to dBm

    Parameters
    ----------
    x : float
        RMS voltage in Volts
    R0 : float
        Load resistance in Ohms

    Returns
    -------
    dBm : float
        Power in dBm
    """
    mP = x**2 / R0 * 1e3
    dBm = 10 * np.log10(mP)
    return dBm
