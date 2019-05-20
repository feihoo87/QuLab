import re
import sys

from notebook.notebookapp import main
from qulab.utils import ShutdownBlocker

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    with ShutdownBlocker('jupyter-notebook'):
        sys.exit(main())
