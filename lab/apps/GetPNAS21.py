import numpy as np
import skrf as rf
from scipy.optimize import leastsq

from lab import Application


class GetPNAS21(Application):
    async def work(self):
        if self.params.get('power', None) is None:
            self.params['power'] = [self.rc['PNA'].getValue('Power'), 'dBm']
        x = self.rc['PNA'].get_Frequency()
        for i in range(self.settings.get('repeat', 1)):
            self.processToChange(100.0 / self.settings.get('repeat', 1))
            y = np.array(self.rc['PNA'].get_S())
            yield x, np.real(y), np.imag(y)
            self.increaseProcess()

    def pre_save(self, x, re, im):
        if self.status['result']['rows'] > 1:
            x = x[0]
            re = np.mean(re, axis=0)
            im = np.mean(im, axis=0)
        return x, re, im

    @staticmethod
    def plot(fig, obj):
        x, re, im = obj
        s = re + 1j * im
        ax = fig.add_subplot(111)
        ax.plot(x / 1e9, rf.mag_2_db(np.abs(s)))
        ax.set_xlabel('Frequency / GHz')
        ax.set_ylabel('S21 / dB')

    @staticmethod
    def plotS21(ax, x, s, params):
        f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params
        background = A * (a * (x - f0)**2 + b *
                          (x - f0) + 1) * np.exp(1j * (delay *
                                                       (x - f0) + Aphi))
        Sfit = GetPNAS21.S21(x, f0, QL, Qe, phi)

        ax.axis('equal')
        ax.plot(np.real(s / background), np.imag(s / background), '.')
        ax.plot(np.real(Sfit), np.imag(Sfit))
        ax.set_xlabel(r'$\mathrm{Re}(S21)$')
        ax.set_ylabel(r'$\mathrm{Im}(S21)$')

    @staticmethod
    def plotInvS21(ax, x, s, params):
        f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params
        background = A * (a * (x - f0)**2 + b *
                          (x - f0) + 1) * np.exp(1j * (delay *
                                                       (x - f0) + Aphi))
        invSfit = GetPNAS21.invS21(
            np.linspace(x[0], x[-1], 10 * len(x)), f0, Qi, Qe, phi)

        ax.axis('equal')
        ax.plot(np.real(background / s), np.imag(background / s), '.')
        ax.plot(np.real(invSfit), np.imag(invSfit))
        ax.set_xlabel(r'$\mathrm{Re}(S21^{-1})$')
        ax.set_ylabel(r'$\mathrm{Im}(S21^{-1})$')

    @staticmethod
    def plotReIm(ax, x, s, params, method='Yale'):
        f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params
        background = A * (a * (x - f0)**2 + b *
                          (x - f0) + 1) * np.exp(1j * (delay *
                                                       (x - f0) + Aphi))
        if method == 'UCSB':
            Sfit = 1 / GetPNAS21.invS21(x, f0, Qi, Qe, phi)
        else:
            Sfit = GetPNAS21.S21(x, f0, QL, Qe, phi)

        ax.plot(x / 1e9, np.real(s / background), '.', label='Re(S21) Data')
        ax.plot(x / 1e9, np.real(Sfit), label='Re(S21)')
        ax.plot(x / 1e9, np.imag(s / background), '.', label='Im(S21) Data')
        ax.plot(x / 1e9, np.imag(Sfit), label='Im(S21)')
        ax.set_xlabel(r'$f/\mathrm{GHz}$')
        ax.legend()

    @staticmethod
    def plotMagAng(ax, x, s, params, method='Yale'):
        f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params
        background = A * (a * (x - f0)**2 + b *
                          (x - f0) + 1) * np.exp(1j * (delay *
                                                       (x - f0) + Aphi))
        if method == 'UCSB':
            Sfit = 1 / GetPNAS21.invS21(x, f0, Qi, Qe, phi)
        else:
            Sfit = GetPNAS21.S21(x, f0, QL, Qe, phi)

        ax.plot(
            x / 1e9,
            rf.mag_2_db(np.abs(s / background)),
            '.',
            label='|S21| Data')
        ax.plot(x / 1e9, rf.mag_2_db(np.abs(Sfit)), label='|S21|')
        ax.set_xlabel(r'$f/\mathrm{GHz}$')
        ax.set_ylabel(r'$|S21| / \mathrm{dB}$')

        ax2 = ax.twinx()
        ax2.plot(
            x / 1e9,
            np.angle(s / background) * 180 / np.pi,
            '.r',
            label='Ang(S21) Data')
        ax2.plot(x / 1e9, np.angle(Sfit) * 180 / np.pi, 'g', label='Ang(S21)')
        ax2.set_ylabel(r'$\mathrm{Ang}(S21) / \degree$')

        ax.legend()
        ax2.legend()

    def analyzer(self, record, params=None, method='UCSB', level=3, skep=0):
        x_raw, re, im = record.data
        s_raw = re + 1j * im
        x, s = self.preFit(x_raw, s_raw)
        if 'start' in record.params.keys():
            start, stop = int(record.params['start'][0]), int(
                record.params['stop'][0])
        else:
            start, stop = 0, len(x)

        return self.analyze(x, s, start, stop, params, method, level, skep)

    def analyze(self, x, s,
                start=0, stop=0,
                params=None,
                method='UCSB',
                level=3, skep=0):
        if stop == 0:
            stop = len(x)

        if method == 'UCSB':
            fitMethod = self.fitUCSB
        elif method == 'Yale':
            fitMethod = self.fitYale

        if params is None:
            params = fitMethod(x[start:stop], s[start:stop])
        if skep < 1:
            params = fitMethod(x[start:stop], s[start:stop], params)
        if level >= 2 and skep < 2:
            params = fitMethod(x, s, params, with_delay=True)
        if level >= 3 and skep < 3:
            params = fitMethod(
                x, s, params, with_delay=True, with_high_order=True)
        return x, s, params

    def fitYale(self, x, s,
                params=None,
                with_delay=False,
                with_high_order=False):
        """"""

        def err(params,
                f,
                s21,
                with_delay=with_delay,
                with_high_order=with_high_order):
            f0, QL, Qe, phi, A, Aphi, delay, a, b = params
            background = A * (with_high_order *
                              (a * (f - f0)**2 + b *
                               (f - f0)) + 1) * np.exp(1j *
                                                       (with_delay * delay *
                                                        (f - f0) + Aphi))
            y = s21 - self.S21(f, f0, QL, Qe, phi) * background
            return np.abs(y)

        if params is None:
            f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = self.guessParams(
                x, s, method='Yale')
        else:
            f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params

        res = leastsq(err, [f0, QL, Qe, phi, A, Aphi, delay, a, b], (x, s))
        f0, QL, Qe, phi, A, Aphi, delay, a, b = res[0]
        Qi = 1 / (1 / QL - 1 / Qe)
        return f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b

    def fitUCSB(self, x, s,
                params=None,
                with_delay=False,
                with_high_order=False):
        """"""

        def err(params,
                f,
                s21,
                with_delay=with_delay,
                with_high_order=with_high_order):
            f0, Qi, Qe, phi, A, Aphi, delay, a, b = params
            background = A * (with_high_order *
                              (a * (f - f0)**2 + b *
                               (f - f0)) + 1) * np.exp(1j *
                                                       (with_delay * delay *
                                                        (f - f0) + Aphi))
            y = 1 / s21 - self.invS21(f, f0, Qi, Qe, phi) / background
            return np.abs(y)

        if params is None:
            f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = self.guessParams(
                x, s, method='UCSB')
        else:
            f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b = params

        res = leastsq(err, [f0, Qi, Qe, phi, A, Aphi, delay, a, b], (x, s))
        f0, Qi, Qe, phi, A, Aphi, delay, a, b = res[0]
        QL = 1 / (1 / Qi + 1 / Qe)
        return f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b

    @staticmethod
    def S21(f, f0, QL, Qe, phi):
        #Qi = 1/(1/QL-1/Qe)
        return 1 - (np.abs(QL) / np.abs(Qe) * np.exp(1j * phi)) / (
            1 + 2j * np.abs(QL) * (np.abs(f) / np.abs(f0) - 1))

    @staticmethod
    def invS21(f, f0, Qi, Qe, phi):
        #QL = 1/(1/Qi+1/Qe)
        return 1 + (Qi / np.abs(Qe) * np.exp(1j * phi)) / (
            1 + 2j * Qi * (np.abs(f) / np.abs(f0) - 1))

    @staticmethod
    def preFit(x, s):
        A = np.poly1d(np.polyfit(x, np.abs(s), 1))
        #s /= np.linspace(np.abs(s[0]), np.abs(s[-1]), len(s))
        phi = np.unwrap(np.angle(s), 0.9 * np.pi)
        #s = s / np.exp(1j*np.linspace(phi[0], phi[-1], len(phi)))
        phase = np.poly1d(np.polyfit(x, phi, 1))
        s = s / A(x) / np.exp(1j * phase(x))
        return x, s

    @staticmethod
    def circleLeastFit(x, y):
        def circle_err(params, x, y):
            xc, yc, R = params
            return (x - xc)**2 + (y - yc)**2 - R**2

        p0 = [
            x.mean(),
            y.mean(),
            np.sqrt(((x - x.mean())**2 + (y - y.mean())**2).mean())
        ]
        res = leastsq(circle_err, p0, (x, y))
        return res[0]

    @staticmethod
    def guessParams(x, s, method='UCSB'):
        if method == 'Yale':
            y = np.abs(s)
            f0 = x[y.argmin()]
            _bw = x[y < 0.5 * (y.max() + y.min())]
            FWHM = max(_bw) - min(_bw)
            QL = f0 / FWHM
            _, _, R = GetPNAS21.circleLeastFit(np.real(s), np.imag(s))
            Qe = QL / (2 * R)
            Qi = 1 / (1 / QL - 1 / Qe)
        elif method == 'UCSB':
            y = np.abs(1 / s)
            f0 = x[y.argmax()]
            _bw = x[y > 0.5 * (y.max() + y.min())]
            FWHM = max(_bw) - min(_bw)
            Qi = f0 / FWHM
            _, _, R = GetPNAS21.circleLeastFit(np.real(1 / s), np.imag(1 / s))
            Qe = Qi / (2 * R)
            QL = 1 / (1 / Qi + 1 / Qe)
        else:
            return
        #       f0, Qi, Qe, QL, phi, A, Aphi, delay, a, b
        return [f0, Qi, Qe, QL, 0, 1, 0, 0, 0, 0]
