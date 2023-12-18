import itertools
import re
from typing import Callable

from .config import style
from .qt_compat import AlignRight, QtWidgets


def matched_xy_pairs(patterns: str, lst: list[str]) -> list[tuple[str, str]]:
    patterns = patterns.replace(" ", "").split(";")
    pairs = []
    for x, y in itertools.product(lst, repeat=2):
        test = f"{x},{y}"
        for pattern in patterns:
            r = re.match(pattern, test)
            if r and r.group(0) == test:
                pairs.append((x, y))
                break
    return pairs


class FormatCombo(QtWidgets.QComboBox):

    def __init__(self):
        super().__init__()
        self.on_change_callable = None

    def set_on_change_event_action(self, callback: Callable[[], None]):
        self.on_change_callable = callback
        self.activated.connect(callback)

    def set_idx(self, idx: int):
        self.setCurrentIndex(idx)
        if (callable(self.on_change_callable)):
            self.on_change_callable()


class XFormatCombo(FormatCombo):

    def __init__(self):
        super().__init__()
        self.addItem("real")
        self.addItem("imag")
        self.addItem("mag")
        self.addItem("phase")


class YFormatCombo(FormatCombo):

    def __init__(self):
        super().__init__()
        self.addItem("mag")
        self.addItem("phase")
        self.addItem("real")
        self.addItem("imag")


class LineEdit(QtWidgets.QLineEdit):

    def set_on_change_event_action(self, callback: Callable[[], None]):
        self.on_change_callable = callback
        self.editingFinished.connect(callback)

    def set_text(self, w):
        self.setText(w)
        if (callable(self.on_change_callable)):
            self.on_change_callable()


class SelectionBundle():

    def __init__(self):
        self.stx = LineEdit()
        # select text
        self.fx = XFormatCombo()
        self.fy = YFormatCombo()
        self.lx = QtWidgets.QCheckBox("logX")
        self.ly = QtWidgets.QCheckBox("logY")
        self.linkx = QtWidgets.QCheckBox("ShareX")
        self.linky = QtWidgets.QCheckBox("ShareY")
        self.sels = []
        # tuple enumeration

    def set_on_change_event_actions(self, on_text_edited, on_format_changed,
                                    on_log_scale_marker_changed):
        self.stx.set_on_change_event_action(on_text_edited)
        self.fx.set_on_change_event_action(on_format_changed)
        self.fy.set_on_change_event_action(on_format_changed)
        self.lx.toggled.connect(on_format_changed)
        self.ly.toggled.connect(on_format_changed)
        self.linkx.toggled.connect(on_log_scale_marker_changed)
        self.linky.toggled.connect(on_log_scale_marker_changed)

    def rm4l(self):  # remove from layout
        self.stx.setParent(None)
        self.fx.setParent(None)
        self.fy.setParent(None)
        self.lx.setParent(None)
        self.ly.setParent(None)
        self.linkx.setParent(None)
        self.linky.setParent(None)

    def a2l(self, layout):  # add to layout
        i = 3
        layout.addWidget(self.stx, 0, i)
        i += 2
        layout.addWidget(self.fx, 0, i)
        i += 2
        layout.addWidget(self.fy, 0, i)
        i += 2
        layout.addWidget(self.lx, 0, 10)
        layout.addWidget(self.ly, 0, 11)
        layout.addWidget(self.linkx, 0, 12)
        layout.addWidget(self.linky, 0, 13)


class ToolBar(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        # the buttons
        # button for points
        self.mode = 'P'
        self.setStyleSheet(style)

        self.pb = QtWidgets.QRadioButton('Points')
        self.pb.setChecked(True)
        self.pb.toggled.connect(self.toggle_mode)

        # button for Traces
        self.tb = QtWidgets.QRadioButton('Traces')
        self.tb.toggled.connect(self.toggle_mode)

        # text labels
        self.ytxt_lb = QtWidgets.QLabel("(X,Y)")
        self.ytxt_lb.setAlignment(AlignRight)
        self.fx_lb = QtWidgets.QLabel("fx")
        self.fx_lb.setAlignment(AlignRight)
        self.fy_lb = QtWidgets.QLabel("fy")
        self.fy_lb.setAlignment(AlignRight)

        # enumeration
        ps = SelectionBundle()
        ps.set_on_change_event_actions(self.textEdited, self.generateXYFM,
                                       self.link_edited)

        ts = SelectionBundle()
        ts.set_on_change_event_actions(self.textEdited, self.generateXYFM,
                                       self.link_edited)

        # connections :
        self.ps = ps
        self.ts = ts

        # plot format configures
        self.xypairs = []
        self.xypairs_dirty = True
        self.fx = None
        self.fy = None
        self.xyfm_dirty = True
        self.link_dirty = True
        self.lx = False
        self.ly = False
        # setting layout
        self.layout = QtWidgets.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.layout.addWidget(self.pb, 0, 0)
        self.layout.addWidget(self.tb, 0, 1)

        self.layout.addWidget(self.ytxt_lb, 0, 2)
        self.layout.addWidget(self.fx_lb, 0, 4)
        self.layout.addWidget(self.fy_lb, 0, 6)

        self.AR = QtWidgets.QPushButton("AR")
        self.AR.setMaximumWidth(30)
        self.AR.setToolTip("Auto Range")
        self.CR = QtWidgets.QPushButton("CLR")
        self.CR.setMaximumWidth(30)
        self.CR.setToolTip("Clearing History Plots")
        self.CR_flag = False
        self.layout.addWidget(self.AR, 0, 8)
        self.layout.addWidget(self.CR, 0, 9)

        self.refresh_layout()

    @property
    def column_names(self) -> list[str]:
        return {
            "P": self.mainwindow.point_data_box.column_names,
            "T": self.mainwindow.trace_data_box.column_names
        }[self.mode]

    @property
    def selections(self) -> SelectionBundle:
        return {"P": self.ps, "T": self.ts}[self.mode]

    def set_trace_text(self, text: str):
        self.ts.stx.set_text(text)

    def set_point_text(self, text: str):
        self.ps.stx.set_text(text)

    def sharexy(self):
        return self.selections.linkx.isChecked(
        ), self.selections.linky.isChecked()

    def set_mainwindow(self, mainwindow):
        self.mainwindow = mainwindow
        self.AR.clicked.connect(self.mainwindow.all_enable_auto_range)
        self.CR.clicked.connect(self.CR_action)

    def AR_action(self):
        self.mainwindow.enable_all_auto_range()

    def CR_action(self):
        self.CR_flag = True

    def refresh_layout(self):
        if self.mode == 'P':
            self.ts.rm4l()
            self.ps.a2l(self.layout)
        elif self.mode == 'T':
            self.ps.rm4l()
            self.ts.a2l(self.layout)

    def toggle_mode(self):
        if (self.pb.isChecked()):
            self.mode = 'P'
        elif (self.tb.isChecked()):
            self.mode = 'T'
        self.refresh_layout()
        self.refresh_comb()

    def refresh_comb(self, ):
        self.generateXYFM()
        self.textEdited()
        #set tooltips
        self.ytxt_lb.setToolTip(str(self.column_names))

    def link_edited(self):
        # print("LinkEdited")
        self.link_dirty = True

    def generateXYFM(self):
        self.fx = self.selections.fx.currentText()
        self.fy = self.selections.fy.currentText()
        self.lx = self.selections.lx.isChecked()
        self.ly = self.selections.ly.isChecked()
        self.xyfm_dirty = True
        #self.show_info() ;

    def textEdited(self):
        new_pairs = matched_xy_pairs(self.selections.stx.text(),
                                     self.column_names)
        if (len(self.xypairs) != len(new_pairs)):
            self.xypairs_dirty = True
        else:
            for i, xy in enumerate(new_pairs):
                if (xy != self.xypairs[i]):
                    self.xypairs_dirty = True
                    break
        self.xypairs = new_pairs
