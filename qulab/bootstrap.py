import functools

from qulab.storage.connect import require_db
from qulab.storage.schema import Notebook, createCodeSnippet

__current_notebook = Notebook()


def get_current_notebook():
    return __current_notebook


def get_inputCells():
    if hasattr(sys.modules['__main__'], 'In'):
        return sys.modules['__main__'].In
    else:
        return ['']


@require_db
def save_inputCells():
    notebook = get_current_notebook()
    aready_saved = len(notebook.inputCells)
    for cell in get_inputCells()[aready_saved:]:
        notebook.inputCells.append(createCodeSnippet(cell))
    notebook.save()
