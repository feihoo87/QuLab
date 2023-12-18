from .config import COL_SEL, COL_UNSEL, SymSize, defualt_colors, ridx, widths
from .qt_compat import QtWidgets

# the plotting widget
try:
    import pyqtgraph as pg
except:
    raise ImportError("Please install pyqtgraph first")

try:
    import pyperclip as pc
    hasCliper = True
except:
    hasCliper = False


class PlotWidget(pg.PlotWidget):

    def __init__(self, minimum_height=300, colors=None):
        self.XAxisLinked = False
        self.YAxisLinked = False
        if colors is None:
            colors = defualt_colors
        elif len(colors) < len(defualt_colors):
            colors.extend(defualt_colors[len(colors):])
        self.colors = colors
        self.xname = ""
        self.yname = ""
        super().__init__()

        self.setMinimumHeight(minimum_height)
        self.showGrid(x=True, y=True)
        self.setBackground(COL_UNSEL)

        self.plotItem.vb.autoRange()

        ## Labeling
        self.XLabel = QtWidgets.QLabel(self)
        self.XLabel.setText("X:")
        self.XLabel.move(0, 5)
        self.YLabel = QtWidgets.QLabel(self)
        self.YLabel.setText("Y:")
        self.YLabel.move(0, 35)

        self.plots = {}
        self.clippos1 = 0
        self.clippos2 = 0
        self.range_select = False
        for i in ridx:
            self.plots[i] = \
              self.plot([],[] ,pen={"color":self.colors[i]  ,"width":widths[i]} ,
                  symbolBrush = self.colors[i],
                  symbolPen = { "width":0 ,"color":self.colors[i] }   ,
                  symbolSize =SymSize[i] ,
              )
        self.update()

    def set_X_label(self, w):
        self.xname = w
        self.XLabel.setText(f"X:{w}")

    def set_Y_label(self, w):
        self.yname = w
        self.YLabel.setText(f"Y:{w}")

    def auto_range(self):
        self.plotItem.vb.autoRange()

    def enable_auto_range(self):
        self.plotItem.vb.enableAutoRange()

    def keyPressEvent(self, ev):
        #print(ev.text());
        tx = ev.text()
        if ('f' == tx or 'F' == tx):
            self.plotItem.vb.autoRange()
        if ('a' == tx or 'A' == tx):
            self.plotItem.vb.setAutoPan()
        if ('r' == tx or 'R' == tx):
            self.range_select = True
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        #print(ev.text());
        tx = ev.text()
        if ('f' == tx or 'F' == tx):
            self.plotItem.vb.autoRange()
        if ('a' == tx or 'A' == tx):
            self.plotItem.vb.setAutoPan()
        if ('r' == tx or 'R' == tx):
            self.range_select = False
        super().keyReleaseEvent(ev)

    def mousePressEvent(self, ev):
        if (4 == ev.button()):
            # print(ev.flags())
            if (hasCliper):
                # print("Mouse is pressed")
                self.clippos1 = self.plotItem.vb.mapSceneToView(ev.pos()).x()
        else:
            super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if (4 == ev.button()):
            p = ev.pos()
            if (hasCliper):
                # print("Mouse is released")
                self.clippos2 = self.plotItem.vb.mapSceneToView(ev.pos()).x()
                if (self.range_select):
                    pc.copy(f"{self.clippos1},{self.clippos2}")
                else:
                    pc.copy(self.clippos2)
        else:
            super().mouseReleaseEvent(ev)

    def update(self):
        super().update()

    def set_data(self, i, x, y):
        self.plots[i].setData(x, y)

    # def mouseDoubleClickEvent(self, ev):
    #     super().mouseDoubleClickEvent(ev)
