from typing import Any, Sequence

import nevergrad as ng
import numpy as np
from scipy.optimize import OptimizeResult


class NgOptimizer():

    def __init__(self, variables, **kwds):
        self._all_x, self._all_y = [], []
        self.config = {
            'method': 'TBPSA',
            'budget': 100,
        }
        self.config.update(kwds)
        instrum = []
        self.dimensions = variables
        for space in variables:

            if space.transform_ == "normalize":
                instrum.append(ng.p.Scalar(init=0.5, lower=0, upper=1))
            else:
                if space.prior == "log-uniform":
                    instrum.append(
                        ng.p.Log(init=None,
                                 exponent=space.base,
                                 lower=space.low,
                                 upper=space.high))
                else:
                    instrum.append(
                        ng.p.Scalar(init=None,
                                    lower=space.low,
                                    upper=space.high))
        self.instrum = ng.p.Instrumentation(*instrum)
        self.opt = getattr(ng.optimizers,
                           self.config['method'])(self.instrum,
                                                  budget=self.config['budget'])

    def suggest(self, *suggested):
        suggested = [
            space.transform(x) for x, space in zip(suggested, self.dimensions)
        ]
        self.opt.suggest(*suggested)

    def ask(self):
        tmp = self.opt.ask()
        return [
            space.inverse_transform(x)
            for x, space in zip(tmp.args, self.dimensions)
        ]

    def tell(self, suggested: Sequence, value: Any):
        self._all_x.append(suggested)
        self._all_y.append(value)
        suggested = tuple([
            space.transform(x) for x, space in zip(suggested, self.dimensions)
        ])
        # self.opt.suggest(*suggested)
        # x = self.opt.ask()
        x = self.instrum.spawn_child(new_value=(suggested, {}))
        self.opt.tell(x, value)

    def get_result(self, history: bool = False) -> OptimizeResult:
        recommendation = self.opt.provide_recommendation()
        ret = OptimizeResult({
            'x': [
                space.inverse_transform(x)
                for x, space in zip(recommendation.args, self.dimensions)
            ]
        })
        if history:
            ret.x_iters = self._all_x
            ret.func_vals = self._all_y
        ret.fun = recommendation.value
        return ret
