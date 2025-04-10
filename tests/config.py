config = {
    '__version__': 1,
    'station': {
        'name': "TestStation",
        'instruments': {},
        'channels': {
            'PSG': {
                "ReadLO": {
                    "port": {
                        "instrument": "PSG126",
                        "channel": 1
                    },
                    "params": {},
                    "status": {
                        "frequency": 6990000000.0,
                        "power": 19
                    },
                    "calibrations": {}
                },
                "LO1": {
                    "port": {
                        "instrument": "PSG102",
                        "channel": 1
                    },
                    "params": {},
                    "status": {
                        "frequency": 4700000000.0,
                        "power": 18
                    },
                    "calibrations": {}
                },
                "LO2": {
                    "port": {
                        "instrument": "PSG105",
                        "channel": 1
                    },
                    "params": {},
                    "status": {
                        "frequency": 4350000000.0,
                        "power": 21
                    },
                    "calibrations": {}
                }
            },
            'AWG': {
                "RI1": {
                    "port": {
                        "instrument": "AWG153",
                        "channel": 1
                    },
                    "params": {
                        "sampleRate": 2000000000
                    },
                    "status": {},
                    "calibrations": {}
                },
                "RQ1": {
                    "port": {
                        "instrument": "AWG153",
                        "channel": 2
                    },
                    "params": {
                        "sampleRate": 2000000000
                    },
                    "status": {},
                    "calibrations": {}
                },
                "X1": {
                    "port": {
                        "instrument": "AWG153",
                        "channel": 3
                    },
                    "params": {
                        "sampleRate": 2000000000
                    },
                    "status": {},
                    "calibrations": {}
                },
                "X2": {
                    "port": {
                        "instrument": "AWG153",
                        "channel": 4
                    },
                    "params": {
                        "sampleRate": 2000000000
                    },
                    "status": {},
                    "calibrations": {}
                },
                "Z": {
                    "port": {
                        "instrument": "AWG154",
                        "channel": 1
                    },
                    "params": {
                        "sampleRate": 2000000000
                    },
                    "status": {},
                    "calibrations": {}
                }
            },
            'AD': {
                "T1": {
                    "port": {
                        "instrument": "AD5",
                        "channel": 1
                    },
                    "params": {
                        "sampleRate": 1000000000
                    },
                    "status": {},
                    "calibrations": {}
                }
            }
        },
        'params': {},
        'status': {},
        'calibrations': {}
    },
    'chip': {
        'qubits': {
            'Q1': {
                "params": {
                    "f01": 4675808085.0,
                    "fr": 6878360000.0,
                    "alpha": -220000000.0,
                    "Ec": 220000131.4583817,
                    "EJ": 13682610474.65348
                },
                "couplers": ["C1"],
                "readoutLine": "T1",
                "channels": {
                    "RF": {
                        "LO": "PSG.LO1",
                        "I": "AWG.X1",
                        "filter": {
                            "pass": [[4500000000.0, 5500000000.0]]
                        }
                    }
                },
                "status": {},
                "calibrations": {},
                "ports": {
                    "X": "E22"
                }
            },
            'Q2': {
                "params": {
                    "f01": 4354224549.0,
                    "fr": 6922480000.0,
                    "alpha": -220000000.0,
                    "Ec": 219996125.653258,
                    "EJ": 11953396604.186008
                },
                "couplers": ["C1"],
                "readoutLine": "T1",
                "channels": {
                    "RF": {
                        "LO": "PSG.LO2",
                        "I": "AWG.X2",
                        "filter": {
                            "pass": [[3500000000.0, 4500000000.0]]
                        }
                    }
                },
                "status": {},
                "calibrations": {},
                "ports": {
                    "X": "E22"
                }
            }
        },
        'couplers': {
            'C1': {
                "params": {},
                "qubits": ["Q1", "Q2"],
                "channels": {
                    "Z": "AWG.Z"
                },
                "status": {
                    "flux": 0
                },
                "calibrations": {},
                "ports": {
                    "Z": "E14"
                }
            }
        },
        'readoutLines': {
            'T1': {
                "params": {},
                "qubits": ["Q1", "Q2"],
                "channels": {
                    "AD": {
                        "IQ": "AD.T1",
                        "LO": "PSG.ReadLO",
                        "trigger": "AWG.RI1.Marker1",
                        "triggerDelay": 5e-07
                    },
                    "RF": {
                        "I": "AWG.RI1",
                        "LO": "PSG.ReadLO",
                        "Q": "AWG.RQ1"
                    }
                },
                "status": {},
                "calibrations": {}
            }
        },
        'params': {},
        'status': {},
        'calibrations': {
            'fluxCrosstalk': [],
            'rfCrosstalk': []
        }
    },
    'gates': {
        'Measure': {
            "Q1": {
                "type": "default",
                "signal": "state",
                "params": {
                    "frequency": 6877810000.0,
                    "duration": 2e-06,
                    "amp": 0.052,
                    "phi": 1.0747615082142474,
                    "threshold": -7538894149.596176
                }
            },
            "Q2": {
                "type": "default",
                "params": {
                    "frequency": 6922130000.0,
                    "duration": 2e-06,
                    "amp": 0.0765,
                    "phi": -2.7392096351071875,
                    "threshold": -8834892453.479649
                }
            }
        },
        'Reset': {},
        'rfUnitary': {
            "Q1": {
                "type": "default",
                "params": {
                    "shape": "CosPulse",
                    "frequency": 4675808085.0,
                    "amp": [[0, 1], [0, 0.8204]],
                    "duration": [[0, 1], [2e-08, 2e-08]],
                    "phase": [[-1, 1], [-1, 1]],
                    "DRAGScaling": 4.1793023176316093e-10
                }
            },
            "Q2": {
                "type": "default",
                "params": {
                    "shape": "CosPulse",
                    "frequency": 4354202438.483826,
                    "amp": [[0, 1], [0, 0.658]],
                    "duration": [[0, 1], [2e-08, 2e-08]],
                    "phase": [[-1, 1], [-1, 1]],
                    "DRAGScaling": 9.866314574173999e-10
                }
            }
        },
        'CZ': {
            "Q1,Q2": {
                "type": "default",
                "params": {
                    "duration": 5e-08,
                    "amp": 0,
                    "edge": 0,
                    "phi1": 0,
                    "phi2": 0
                }
            }
        },
        'iSWAP': {
            "Q1,Q2": {
                "type": "default",
                "params": {
                    "frequency": 318407000.0,
                    "duration": 1.93e-07,
                    "offset": 0,
                    "amp": 0.8,
                    "phase": 0,
                    "phi1": 0,
                    "phi2": 0
                }
            }
        },
        'CR': {
            '__order_senstive__': True,
            'Q1,Q2': {
                "type": "default",
                "params": {}
            },
            'Q2,Q1': {
                "type": "default",
                "params": {}
            },
        }
    }
}
