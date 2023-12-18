from multiprocessing import Queue
from typing import Literal

from .config import forms, ridx, style
from .dataset import Dataset
from .event_queue import EventQueue
from .ploter import PlotWidget
from .qt_compat import (BottomDockWidgetArea, QtCore, QtWidgets,
                        ScrollBarAlwaysOff, ScrollBarAlwaysOn,
                        TopDockWidgetArea)
from .toolbar import ToolBar


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self,
                 queue: Queue,
                 ncols=3,
                 plot_minimum_height=350,
                 plot_colors: list[tuple[int, int, int]] | None = None):
        super().__init__()
        self.ncols = ncols
        self.need_reshuffled = False
        self.plot_minimum_height = plot_minimum_height
        self.plot_widgets: list[PlotWidget] = []
        self.plot_colors = plot_colors
        self.toolbar = ToolBar()
        self.trace_data_box = Dataset()
        self.point_data_box = Dataset()
        self.queue = EventQueue(queue, self.toolbar, self.point_data_box,
                                self.trace_data_box)

        self.init_ui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(250)

    def init_ui(self):
        self.setStyleSheet(style)
        self.setMinimumHeight(500)
        self.setMinimumWidth(700)
        self.scroll = QtWidgets.QScrollArea(
        )  # Scroll Area which contains the widgets, set as the centralWidget
        self.widget = QtWidgets.QWidget(
        )  # Widget that contains the collection of Vertical Box
        self.layout = QtWidgets.QGridLayout()
        self.widget.setLayout(self.layout)

        #Scroll Area Properties
        #self.setCorner(Qt.TopSection, Qt.TopDockWidgetArea);
        self.scroll.setVerticalScrollBarPolicy(ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)
        self.setCentralWidget(self.scroll)

        self.dock = QtWidgets.QDockWidget(self)
        self.dock.setAllowedAreas(TopDockWidgetArea | BottomDockWidgetArea)
        self.addDockWidget(TopDockWidgetArea, self.dock)
        self.dock.setFloating(False)
        self.dock.setWidget(self.toolbar)
        self.dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)
        #self.tabifyDockWidget(self.dock,None);
        #self.addDockWidget(self.dock);
        #self.setStatusBar(self.toolbar);
        #self.layout.addWidget(self.toolbar , 0 , 0  , 1, self.ncol);

        self.setWindowTitle('Scroll multi view')
        self.show()
        self.toolbar.set_mainwindow(self)
        self.toolbar.pb.setChecked(True)

    @property
    def mode(self) -> Literal["P", "T"]:
        return self.toolbar.mode

    @property
    def dataset(self) -> Dataset:
        return {"P": self.point_data_box, "T": self.trace_data_box}[self.mode]

    def set_ncols(self, x: int):
        x = max(1, min(10, int(x)))
        if (x != self.ncols):
            self.need_reshuffled = True
            self.ncols = x

    def add_subplot(self):
        n = len(self.plot_widgets)
        pw = PlotWidget(self.plot_minimum_height, self.plot_colors)
        self.plot_widgets.append(pw)
        grid_row = n // self.ncols
        grid_col = n % self.ncols
        self.layout.addWidget(pw, grid_row + 1, grid_col)
        return pw

    def create_subplots(self, xy_pairs):
        for xn, yn in xy_pairs:
            pw = self.add_subplot()
            pw.set_X_label(xn)
            pw.set_Y_label(yn)
        self.do_link()
        self.all_enable_auto_range()

    def clear_subplots(self):
        for i in range(len(self.plot_widgets)):
            self.layout.removeWidget(self.plot_widgets[i])
            self.plot_widgets[i].setParent(None)
        self.plot_widgets.clear()

    def remove_plot(self, w: PlotWidget):
        w.setParent(None)
        self.plot_widgets.remove(w)
        self.reshuffle()

    def drop_last_plot(self, i_=-1):
        # delete the one
        i = int(i_)
        if (i < len(self.plot_widgets)):
            w = self.plot_widgets[i]
            w.setParent(None)
            del w
            del self.plot_widgets[i]
        self.reshuffle()

    def reshuffle(self):
        for idx, widget in enumerate(self.plot_widgets):
            widget.setParent(None)
            grid_row = idx // self.ncols
            grid_col = idx % self.ncols
            self.layout.addWidget(widget, grid_row + 1, grid_col)

    def keyPressEvent(self, ev):
        #print(ev.text());
        tx = ev.text()
        if (tx in ['_', '-']):
            self.set_ncols(self.ncols - 1)
        elif (tx in ['=', '+']):
            self.set_ncols(self.ncols + 1)

    def mouse_click(self):
        pass

    def do_link(self):
        """
        link the plot

        share the same x or y axis
        """
        same_X = {}
        xy_pairs = self.toolbar.xypairs
        for idx, xyn in enumerate(xy_pairs):
            xn, yn = xyn
            if xn not in same_X:
                same_X[xn] = []
            same_X[xn].append(idx)

        sharex, sharey = self.toolbar.sharexy()

        s_A = not (sharex and sharey)
        for x, yidxs in same_X.items():
            pre_yidx = -1
            for yidx in yidxs:
                if (-1 != pre_yidx):
                    if (s_A):
                        self.plot_widgets[pre_yidx].plotItem.vb.setXLink(None)
                        self.plot_widgets[pre_yidx].plotItem.vb.setYLink(None)

                    if sharex:
                        self.plot_widgets[pre_yidx].plotItem.vb.setXLink(
                            self.plot_widgets[yidx].plotItem.vb)

                    if sharey:
                        self.plot_widgets[pre_yidx].plotItem.vb.setYLink(
                            self.plot_widgets[yidx].plotItem.vb)
                pre_yidx = yidx

    def all_auto_range(self):
        for pw in self.plot_widgets:
            pw.auto_range()

    def all_enable_auto_range(self):
        for pw in self.plot_widgets:
            pw.enable_auto_range()

    def update(self):
        # update the queue
        self.queue.flush()

        rescale = False

        # setup the xyfm
        if (self.toolbar.xypairs_dirty):
            self.clear_subplots()
            self.create_subplots(self.toolbar.xypairs)
            self.toolbar.xypairs_dirty = False
            rescale = True

        if (self.toolbar.link_dirty):
            self.do_link()
            self.toolbar.link_dirty = False

        if (self.need_reshuffled):
            self.need_reshuffled = False
            self.reshuffle()

        # checking the log space
        if (self.toolbar.xyfm_dirty):
            for pw in self.plot_widgets:
                pw.plotItem.ctrl.logXCheck.setChecked(self.toolbar.lx)
                pw.plotItem.ctrl.logYCheck.setChecked(self.toolbar.ly)

        #update the plot
        # if clear is set then do the clear :
        if (self.toolbar.CR_flag):
            self.toolbar.CR_flag = False
            self.dataset.clear_history()
            self.dataset.dirty = True

        if (self.dataset.dirty or self.toolbar.xyfm_dirty or rescale):
            self.dataset.dirty = False
            self.xyfm_dirty = False
            for pw in self.plot_widgets:

                fx = forms[self.toolbar.fx]
                fy = forms[self.toolbar.fy]
                for i in ridx:
                    x, y = self.dataset.get_data(i, pw.xname, pw.yname)
                    l = min(len(x), len(y))
                    x, y = fx(x[:l], 0), fy(y[:l], 0)
                    pw.set_data(i, x, y)
                pw.update()
                if rescale:
                    pw.auto_range()
