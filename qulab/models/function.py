import inspect
import time
from typing import Callable

import numpy as np
from lmfit import Model, Parameters, create_params, minimize


def model(x, a, b, c, d, T, o):
    x = 2 * np.pi * (x - o) / T
    return a * np.cos(4 * x) + b * np.cos(2 * x) + c * np.cos(x) + d


class Function():

    def __init__(
        self,
        model: Callable | Model,
        params: Parameters | None = None,
        tolerance=1e-6,
        tau=None,
        retry=100,
    ):
        self.data = {'time': [], 'x': [], 'y': []}
        self.tau = tau
        self.model = model

        if isinstance(model, Model) and params is None:
            self.params = model.make_params()
        elif params is not None:
            self.params = params
        else:
            self.params = Parameters()
            for name, param in inspect.signature(model).parameters.items():
                if param.name == 'x':
                    continue
                if param.default == inspect.Parameter.empty:
                    value = 0
                else:
                    value = param.default
                self.params.add(name, value=value, min=-np.inf, max=np.inf)
        self.tolerance = tolerance
        self.retry = retry

    def __call__(self, x):
        #self.fit(time.time())
        params = self.params.valuesdict()
        return self.model(x, **params)

    def append(self, x, y):
        self.data['x'].append(x)
        self.data['y'].append(y)
        self.data['time'].append(time.time())

    def fit(self, time):
        x = np.array(self.data['x'])
        y = np.array(self.data['y'])
        t = time - np.array(self.data['time'])
        if self.tau is None:
            w = np.ones_like(t)
        else:
            w = np.exp(-t / self.tau)
        w = w / np.mean(w)

        params = self.params
        for _ in range(self.retry):
            result = minimize(
                self.residual,
                params,
                args=(x, y, w),
                method='leastsq',
                nan_policy='omit',
                scale_covar=True,
            )
            fvec = self.residual(params, x, y, w)
            if np.sqrt(np.mean(fvec**2)) < self.tolerance:
                break
            params = create_params()
            for name, param in self.params.items():
                if param.vary:
                    if param.min is not None and param.max is not None:
                        value = np.random.random() * (param.max -
                                                      param.min) + param.min
                    else:
                        value = np.clip(param.value + np.random.random(),
                                        param.min, param.max)
                    params.add(name,
                               value=value,
                               min=param.min,
                               max=param.max,
                               vary=True)
                else:
                    params.add(name, value=param.value, vary=False)
        else:
            raise RuntimeError(f'Fit failed after {self.retry} retries')
        self.params = result.params

    def residual(self, params: Parameters, x, y, weight):
        return (y - self.model(x, **params.valuesdict())) * weight
