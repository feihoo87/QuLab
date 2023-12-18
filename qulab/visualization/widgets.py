import matplotlib.pyplot as plt
import numpy as np


class DataPicker():

    def __init__(self, ax=None):
        self.points_and_text = {}
        self.points = None
        self.hline = None
        self.vline = None
        self.text = None
        if ax is None:
            ax = plt.gca()
        self.ax = ax
        self.ax.figure.canvas.mpl_connect('button_press_event', self.on_click)
        # self.ax.figure.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.ax.figure.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.mode = 'pick'

    def on_key_press(self, event):
        if event.key == 'a':
            if self.mode != 'pick':
                self.mode = 'pick'
            else:
                self.mode = 'default'

    def on_move(self, event):
        if event.inaxes is self.ax:
            # self.hline = self.ax.axhline(y=np.nan, color='r', lw=1)
            # self.vline = self.ax.axvline(x=np.nan, color='r', lw=1)
            # self.text = self.ax.text(0, 0, '', verticalalignment='center')
            self.hline.set_ydata(event.ydata)
            self.vline.set_xdata(event.xdata)
            self.text.set_position((event.xdata, event.ydata))
            self.text.set_text(f'({event.xdata:.2f}, {event.ydata:.2f})')
            self.ax.draw()

    def on_click(self, event):
        if self.mode != 'pick':
            return
        # 鼠标左键的button值为1
        if event.button == 1 and event.inaxes is self.ax:
            point = (event.xdata, event.ydata)
            text = self.ax.text(point[0],
                                point[1],
                                f'({point[0]:.2f}, {point[1]:.2f})',
                                verticalalignment='center')
            self.points_and_text[point] = text
            x, y = self.get_xy()
            if self.points is None:
                self.points, = self.ax.plot(x, y, 'ro')
            else:
                self.points.set_data(x, y)
            self.ax.draw()

        elif event.button == 3 and event.inaxes is self.ax:
            for point, text in list(self.points_and_text.items()):
                point_xdisplay, point_ydisplay = self.ax.transData.transform_point(
                    point)

                distance = np.sqrt((point_xdisplay - event.x)**2 +
                                   (point_ydisplay - event.y)**2)
                if distance < 10:
                    text.remove()
                    self.points_and_text.pop(point)
                    if self.points_and_text:
                        x, y = self.get_xy()
                        self.points.set_data(x, y)
                    else:
                        self.points.remove()
                        self.points = None
                    self.ax.draw()
                    break

    def get_xy(self):
        if self.points_and_text:
            data = np.asarray(list(self.points_and_text.keys()))
            x, y = data[:, 0], data[:, 1]

            index = np.argsort(x)
            x = np.asarray(x)[index]
            y = np.asarray(y)[index]
            return x, y
        else:
            return np.array([]), np.array([])
