import contextlib
import time
from datetime import datetime

from .storage.crud import create_cell, create_notebook
from .storage.models import Notebook

__current_notebook_id = None


def _get_current_notebook(session):
    global __current_notebook_id
    if __current_notebook_id is None:
        notebook = create_notebook(session, 'Untitled')
        session.commit()
        __current_notebook_id = notebook.id
    else:
        notebook = session.query(Notebook).filter(
            Notebook.id == __current_notebook_id).one()
    return notebook


def _get_current_cell(session):
    notebook = _get_current_notebook(session)
    if notebook.cells:
        return notebook.cells[-1]
    else:
        return None


def _save_inputCells(session, inputCells=None):
    notebook = _get_current_notebook(session)
    aready_saved = len(notebook.cells)
    if inputCells:
        for cell in inputCells[aready_saved:]:
            create_cell(session, notebook, cell)


def _update_inputCells(session):
    cell = _get_current_cell(session)
    if cell:
        cell.ftime = datetime.utcnow()
        session.add(cell)


__sessionmaker = None


@contextlib.contextmanager
def get_session():
    global __session
    if __sessionmaker is None:
        raise RuntimeError('Sessionmaker is not set')
    session = __sessionmaker()
    try:
        yield session
        session.commit()
    except:
        session.rollback()


def set_sessionmaker(sessionmaker):
    global __sessionmaker
    __sessionmaker = sessionmaker


def get_current_notebook(session=None):
    try:
        if session is None:
            with get_session() as session:
                return _get_current_notebook(session)
        else:
            return _get_current_notebook(session)
    except RuntimeError:
        return None


def get_current_cell_id(session=None):
    try:
        if session is None:
            with get_session() as session:
                return _get_current_cell(session).id
        else:
            return _get_current_cell(session).id
    except RuntimeError as e:
        return None


def get_inputCells():
    try:
        from IPython import get_ipython

        return get_ipython().user_ns['In']
    except Exception as e:
        # raise e
        return ['']


def autosave_cells(ipython):
    try:
        with get_session() as session:
            _save_inputCells(session, get_inputCells())
    except:
        pass


def update_timestamp(ipython):
    try:
        with get_session() as session:
            _update_inputCells(session)
    except:
        pass


def setup_ipy_events():
    try:
        from IPython import get_ipython

        ipython = get_ipython()

        if ipython is not None:
            ipython.events.register('pre_run_cell', autosave_cells)
            ipython.events.register('post_run_cell', update_timestamp)
    except:
        pass
