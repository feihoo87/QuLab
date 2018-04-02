import ipywidgets as widgets
from IPython.display import display


class ApplicationUI:
    def __init__(self, app):
        self.app = app
        self._ProgressWidget = widgets.FloatProgress(
            0, description=self.app.__class__.__name__, bar_style='')
        self._PauseButton = widgets.Button(description="Pause")
        self._PauseButton.on_click(self.on_pause_button_clicked)
        self._InterruptButton = widgets.Button(description="Interrupt")
        self._InterruptButton.on_click(self.on_interrupt_button_clicked)
        self.ui = widgets.HBox(
            [self._PauseButton, self._InterruptButton, self._ProgressWidget])

    def setProcess(self, value):
        self._ProgressWidget.value = value

    def on_pause_button_clicked(self, btn):
        if btn.description == 'Pause':
            btn.description = 'Continue'
            self.app.pause()
        else:
            btn.description = 'Pause'
            self.app.continue_()

    def on_interrupt_button_clicked(self, btn):
        if btn.description == 'Interrupt':
            btn.description = 'Restart'
            self.app.interrupt()
        else:
            btn.description = 'Interrupt'
            self._PauseButton.disabled = False
            self.app.restart()

    def display(self):
        display(self.ui)

    def set_start(self):
        self._ProgressWidget.bar_style = ''

    def set_done(self):
        self._ProgressWidget.bar_style = 'success'
        self._InterruptButton.description = 'Restart'
        self._PauseButton.disabled = True
