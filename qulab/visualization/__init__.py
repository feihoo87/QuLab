import matplotlib.pyplot as plt
import numpy as np

from ._autoplot import autoplot


def plotLine(c0, c1, ax, **kwargs):
    t = np.linspace(0, 1, 11)
    c = (c1 - c0) * t + c0
    ax.plot(c.real, c.imag, **kwargs)


def plotCircle(c0, r, ax, **kwargs):
    t = np.linspace(0, 1, 1001) * 2 * np.pi
    s = c0 + r * np.exp(1j * t)
    ax.plot(s.real, s.imag, **kwargs)


def plotEllipse(c0, a, b, phi, ax, **kwargs):
    t = np.linspace(0, 1, 1001) * 2 * np.pi
    c = np.exp(1j * t)
    s = c0 + (c.real * a + 1j * c.imag * b) * np.exp(1j * phi)
    ax.plot(s.real, s.imag, **kwargs)


def plotDistribution(s0,
                     s1,
                     fig=None,
                     axes=None,
                     info=None,
                     hotThresh=10000,
                     logy=False):
    from waveforms.math.fit import get_threshold_info, mult_gaussian_pdf

    if info is None:
        info = get_threshold_info(s0, s1)
    else:
        info = get_threshold_info(s0, s1, info['threshold'], info['phi'])
    thr, phi = info['threshold'], info['phi']
    # visibility, p0, p1 = info['visibility']
    # print(
    #     f"thr={thr:.6f}, phi={phi:.6f}, visibility={visibility:.3f}, {p0}, {1-p1}"
    # )

    if axes is not None:
        ax1, ax2 = axes
    else:
        if fig is None:
            fig = plt.figure()
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

    if (len(s0) + len(s1)) < hotThresh:
        ax1.plot(np.real(s0), np.imag(s0), '.', alpha=0.2)
        ax1.plot(np.real(s1), np.imag(s1), '.', alpha=0.2)
    else:
        _, *bins = np.histogram2d(np.real(np.hstack([s0, s1])),
                                  np.imag(np.hstack([s0, s1])),
                                  bins=50)

        H0, *_ = np.histogram2d(np.real(s0),
                                np.imag(s0),
                                bins=bins,
                                density=True)
        H1, *_ = np.histogram2d(np.real(s1),
                                np.imag(s1),
                                bins=bins,
                                density=True)
        vlim = max(np.max(np.abs(H0)), np.max(np.abs(H1)))

        ax1.imshow(H1.T - H0.T,
                   alpha=(np.fmax(H0.T, H1.T) / vlim).clip(0, 1),
                   interpolation='nearest',
                   origin='lower',
                   cmap='coolwarm',
                   vmin=-vlim,
                   vmax=vlim,
                   extent=(bins[0][0], bins[0][-1], bins[1][0], bins[1][-1]))

    ax1.axis('equal')
    ax1.set_xticks([])
    ax1.set_yticks([])
    for s in ax1.spines.values():
        s.set_visible(False)

    # c0, c1 = info['center']
    # a0, b0, a1, b1 = info['std']
    params = info['params']
    r0, i0, r1, i1 = params[0][0], params[1][0], params[0][1], params[1][1]
    a0, b0, a1, b1 = params[0][2], params[1][2], params[0][3], params[1][3]
    c0 = (r0 + 1j * i0) * np.exp(1j * phi)
    c1 = (r1 + 1j * i1) * np.exp(1j * phi)
    phi0 = phi + params[0][6]
    phi1 = phi + params[1][6]
    plotEllipse(c0, 2 * a0, 2 * b0, phi0, ax1)
    plotEllipse(c1, 2 * a1, 2 * b1, phi1, ax1)

    im0, im1 = info['idle']
    lim = min(im0.min(), im1.min()), max(im0.max(), im1.max())
    t = (np.linspace(lim[0], lim[1], 3) + 1j * thr) * np.exp(-1j * phi)
    ax1.plot(t.imag, t.real, 'k--')

    ax1.plot(np.real(c0), np.imag(c0), 'o', color='C3')
    ax1.plot(np.real(c1), np.imag(c1), 'o', color='C4')

    re0, re1 = info['signal']
    x, a, b, c = info['cdf']

    xrange = (min(re0.min(), re1.min()), max(re0.max(), re1.max()))

    n0, bins0, *_ = ax2.hist(re0, bins=80, range=xrange, alpha=0.5)
    n1, bins1, *_ = ax2.hist(re1, bins=80, range=xrange, alpha=0.5)

    x_range = np.linspace(x.min(), x.max(), 1001)
    *_, cov0, cov1 = info['std']
    ax2.plot(
        x_range,
        np.sum(n0) * (bins0[1] - bins0[0]) *
        mult_gaussian_pdf(x_range, [r0, r1], [
            np.sqrt(cov0[0, 0]), np.sqrt(cov1[0, 0])
        ], [params[0][4], 1 - params[0][4]]))
    ax2.plot(
        x_range,
        np.sum(n1) * (bins1[1] - bins1[0]) *
        mult_gaussian_pdf(x_range, [r0, r1], [
            np.sqrt(cov0[0, 0]), np.sqrt(cov1[0, 0])
        ], [params[0][5], 1 - params[0][5]]))
    ax2.set_ylabel('Count')
    ax2.set_xlabel('Projection Axes')
    if logy:
        ax2.set_yscale('log')
        ax2.set_ylim(0.1, max(np.sum(n0), np.sum(n1)))

    ax3 = ax2.twinx()
    ax3.plot(x, a, '--', lw=1, color='C0')
    ax3.plot(x, b, '--', lw=1, color='C1')
    ax3.plot(x, c, 'k--', alpha=0.5, lw=1)
    ax3.set_ylim(0, 1.1)
    ax3.vlines(thr, 0, 1.1, 'k', alpha=0.5)
    ax3.set_ylabel('Integral Probability')

    return info


ALLXYSeq = [('I', 'I'), ('X', 'X'), ('Y', 'Y'), ('X', 'Y'), ('Y', 'X'),
            ('X/2', 'I'), ('Y/2', 'I'), ('X/2', 'Y/2'), ('Y/2', 'X/2'),
            ('X/2', 'Y'), ('Y/2', 'X'), ('X', 'Y/2'), ('Y', 'X/2'),
            ('X/2', 'X'), ('X', 'X/2'), ('Y/2', 'Y'), ('Y', 'Y/2'), ('X', 'I'),
            ('Y', 'I'), ('X/2', 'X/2'), ('Y/2', 'Y/2')]


def plotALLXY(data, ax=None):
    assert len(data) % len(ALLXYSeq) == 0

    if ax is None:
        ax = plt.gca()

    ax.plot(np.array(data), 'o-')
    repeat = len(data) // len(ALLXYSeq)
    ax.set_xticks(np.arange(len(ALLXYSeq)) * repeat + 0.5 * (repeat - 1))
    ax.set_xticklabels([','.join(seq) for seq in ALLXYSeq], rotation=60)
    ax.grid(which='major')


def plot_mat(rho, title='$\\chi$', cmap='coolwarm'):
    lim = np.abs(rho).max()
    N = rho.shape[0]

    fig = plt.figure(figsize=(6, 4))
    fig.suptitle(title)

    ax1 = plt.subplot(121)
    cax1 = ax1.imshow(rho.real, vmin=-lim, vmax=lim, cmap=cmap)
    ax1.set_title('Re')
    ax1.set_xticks(np.arange(N))
    ax1.set_yticks(np.arange(N))

    ax2 = plt.subplot(122)
    cax2 = ax2.imshow(rho.imag, vmin=-lim, vmax=lim, cmap=cmap)
    ax2.set_title('Im')
    ax2.set_xticks(np.arange(N))
    ax2.set_yticks(np.arange(N))

    plt.subplots_adjust(bottom=0.2, right=0.9, top=0.95)

    cbar_ax = fig.add_axes([0.15, 0.15, 0.7, 0.05])
    cb = fig.colorbar(cax1, cax=cbar_ax, orientation='horizontal')
    plt.show()
