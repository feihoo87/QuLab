import pathlib
import pickle

import click
import dill
import matplotlib.pyplot as plt
import numpy as np

from .qdat import draw as draw_qdat

default_draw_methods = {
    '.qdat': draw_qdat,
}


def load_data(fname):
    try:
        from home.hkxu.tools import get_record_by_id
        record_id = int(str(fname))
        return get_record_by_id(record_id).data
    except:
        pass
    with open(fname, 'rb') as f:
        try:
            data = pickle.load(f)
        except:
            f.seek(0)
            data = dill.load(f)
    return data


def draw_common(data):
    try:
        script = data['meta']['plot_script']
        assert script.strip()
        global_namespace = {'plt': plt, 'np': np, 'result': data}
        exec(script, global_namespace)
    except:
        from home.hkxu.tools import plot_record
        plot_record(data['meta']['id'])


def draw_error(data, text="No validate plot script found"):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, text, ha='center', va='center')
    ax.set_axis_off()
    return fig


@click.command()
@click.argument('fname', default='')
def plot(fname):
    """Plot the data in the file."""
    try:
        fname = pathlib.Path(fname)
        data = load_data(fname)
        try:
            draw_common(data)
        except:
            default_draw_methods.get(fname.suffix, draw_error)(data)
    except FileNotFoundError:
        draw_error(None, text=f"File {fname} not found.")
    except pickle.UnpicklingError:
        draw_error(None, text=f"File {fname} is not a pickle file.")

    plt.show()


if __name__ == '__main__':
    plot()
