import numpy as np
from matplotlib import rcParams, cm
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FCanvas,
    NavigationToolbar2QT as NavBar,
)
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from plottr.utils.num import (
    interp_meshgrid_2d, centers2edges_1d,
    centers2edges_2d
)
from pyqtgraph.Qt import QtGui, QtCore
from ..data.datadict import MeshgridDataDict, meshgrid_to_datadict
from ..node.node import Node
from ..utils import (
    num
)


# TODO: configurable plot options
# TODO: refactor into small plot methods, plot widgets/canvases/data checkers

def setMplDefaults():
    rcParams['figure.dpi'] = 300
    rcParams['figure.figsize'] = (4.5, 3)
    rcParams['savefig.dpi'] = 300
    rcParams['axes.grid'] = True
    rcParams['grid.linewidth'] = 0.5
    rcParams['grid.linestyle'] = ':'
    rcParams['font.family'] = 'Arial'
    rcParams['font.size'] = 6
    rcParams['lines.markersize'] = 4
    rcParams['lines.linestyle'] = '-'
    rcParams['savefig.transparent'] = False
    rcParams['figure.subplot.bottom'] = 0.15
    rcParams['figure.subplot.top'] = 0.85
    rcParams['figure.subplot.left'] = 0.15
    rcParams['figure.subplot.right'] = 0.9


def pcolorgrid(xaxis, yaxis):
    xedges = centers2edges_1d(xaxis)
    yedges = centers2edges_1d(yaxis)
    xx, yy = np.meshgrid(xedges, yedges)
    return xx, yy


def ppcolormesh_from_meshgrid(ax, x, y, z, **kw):
    cmap = kw.get('cmap', cm.viridis)

    x = x.astype(float)
    y = y.astype(float)
    z = z.astype(float)

    if np.ma.is_masked(x):
        x = x.filled(np.nan)
    if np.ma.is_masked(y):
        y = y.filled(np.nan)
    if np.ma.is_masked(z):
        z = z.filled(np.nan)

    if np.all(num.is_invalid(x)) or np.all(num.is_invalid(y)):
        return

    if np.any(np.isnan(x)) or np.any(np.isnan(y)):
        x, y = interp_meshgrid_2d(x, y)

    if np.any(num.is_invalid(x)) or np.any(num.is_invalid(y)):
        x, y, z = num.crop2d(x, y, z)

    for g in x, y, z:
        if g.size == 0:
            return
        elif len(g.shape) < 2:
            return
        elif min(g.shape) < 2:
            im = ax.scatter(x, y, c=z)
            return im

    try:
        x = centers2edges_2d(x)
        y = centers2edges_2d(y)
    except:
        return

    im = ax.pcolormesh(x, y, z, cmap=cmap, **kw)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    return im


class PlotNode(Node):
    nodeName = 'Plot'

    newPlotData = QtCore.pyqtSignal(object)

    def setPlotWidget(self, widget):
        self.plotWidget = widget
        self.newPlotData.connect(self.plotWidget.setData)

    def process(self, **kw):
        data = kw['dataIn']
        self.newPlotData.emit(data)
        return dict(dataOut=data)


class MPLPlot(FCanvas):

    def __init__(self, parent=None, width=4, height=3,
                 dpi=150, nrows=1, ncols=1):

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self.clearFig(nrows, ncols)
        self.setParent(parent)

    def autosize(self):
        self.fig.subplots_adjust(left=0.125, bottom=0.125, top=0.9, right=0.875,
                                 wspace=0.35, hspace=0.2)

    def clearFig(self, nrows=1, ncols=1, naxes=1):
        self.fig.clear()
        setMplDefaults()

        self.axes = []
        iax = 1
        if naxes > nrows * ncols:
            raise ValueError(
                f'Number of axes ({naxes}) larger than rows ({nrows}) x '
                f'columns ({ncols}).')

        for i in range(1, naxes + 1):
            kw = {}
            if iax > 1:
                kw['sharex'] = self.axes[0]
                kw['sharey'] = self.axes[0]

            self.axes.append(self.fig.add_subplot(nrows, ncols, i))
            iax += 1

        # self.fig.tight_layout()
        self.autosize()
        self.draw()
        return self.axes

    def resizeEvent(self, event):
        # self.fig.tight_layout()
        self.autosize()
        super().resizeEvent(event)


class MPLPlotWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        setMplDefaults()

        self.plot = MPLPlot()
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.plot)
        layout.addWidget(NavBar(self.plot, self))

    def setData(self, data):
        raise NotImplementedError


class AutoPlot(MPLPlotWidget):
    # TODO: the y-label generation is a bit crude like this.

    MAXYLABELS = 3

    def _plot1d(self, data, ax, axName, dNames):
        ylabel = ""
        nylabels = 0

        fmt = 'o'
        if isinstance(data, MeshgridDataDict):
            fmt = 'o-'

        for n in dNames:
            x = data[axName]['values']
            y = data[n]['values']
            ax.plot(x, y, fmt, mfc='None', mew=1, lw=0.5, label=n)

            if nylabels < self.MAXYLABELS:
                ylabel += data.label(n)
                ylabel += '; '
                nylabels += 1

        ylabel = ylabel[:-2]
        if len(dNames) > self.MAXYLABELS:
            ylabel += '; [...]'
        ax.set_ylabel(ylabel)
        ax.set_xlabel(data.label(axName))
        ax.legend()
        # self.plot.fig.tight_layout()
        self.plot.autosize()

    def _plot2d(self, data, ax, xName, yName, dName):
        x = data[xName]['values']
        y = data[yName]['values']
        z = data[dName]['values']
        if isinstance(data, MeshgridDataDict):
            im = ppcolormesh_from_meshgrid(ax, x, y, z)
        else:
            im = ax.scatter(x, y, c=z)

        if im is None:
            return

        div = make_axes_locatable(ax)
        cax = div.append_axes("right", size="5%", pad=0.05)
        self.plot.fig.colorbar(im, cax=cax)

        ax.set_title(dName, size='small')
        ax.set_ylabel(data.label(yName))
        ax.set_xlabel(data.label(xName))
        cax.set_ylabel(data.label(dName))

    def setData(self, data):
        if data is None:
            return

        axesNames = data.axes()
        dataNames = data.dependents()
        shape = data.shapes()[dataNames[0]]

        if 0 in shape:
            return
        if len(axesNames) == 2 and isinstance(data, MeshgridDataDict):
            if min(shape) < 2:
                data = meshgrid_to_datadict(data)

        naxes = len(axesNames)
        ndata = len(dataNames)

        if naxes == 0 or ndata == 0:
            self.plot.clearFig(naxes=0)
        elif naxes == 1:
            ax = self.plot.clearFig(1, 1, 1)[0]
            self._plot1d(data, ax, axesNames[0], dataNames)
        elif naxes == 2:
            nrows = ndata ** .5 // 1
            ncols = np.ceil(ndata / nrows)
            axes = self.plot.clearFig(nrows, ncols, ndata)
            for i, dn in enumerate(dataNames):
                ax = axes[i]
                self._plot2d(data, ax, axesNames[0], axesNames[1], dn)

        elif naxes > 2:
            raise ValueError(
                'Cannot plot more than two axes. (given: {})'.format(axesNames))

        # self.plot.fig.tight_layout()
        self.plot.autosize()
        self.plot.draw()
