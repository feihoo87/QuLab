import numpy as np


def entries():
    return [('templates/rabi_in_group.py', f'run/rabi/group{i}.py', {
        'qubits': tuple([f'Q{j}' for j in range(i, 72 - 3 + i, 4)]),
        'amp': np.linspace(0, 2, 11),
    }) for i in range(4)]
