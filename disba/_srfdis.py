"""
This module is a Numba implementation of the Fortran program SRFDIS.

..

    COMPUTER PROGRAMS IN SEISMOLOGY
    VOLUME IV

    COPYRIGHT 1986, 1991
    D. R. Russell, R. B. Herrmann
    Department of Earth and Atmospheric Sciences
    Saint Louis University
    221 North Grand Boulevard
    St. Louis, Missouri 63103
    U. S. A.

"""

import numpy

from ._common import jitted

__all__ = [
    "srfdis",
]


twopi = 2.0 * numpy.pi


@jitted
def dnka(wvno2, gam, gammk, rho, a0, cpcq, cpy, cpz, cqw, cqx, xy, xz, wy, wz):
    """Dunkin's matrix."""
    ca = numpy.zeros((5, 5), dtype=numpy.float64)

    gamm1 = gam - 1.0
    twgm1 = gam + gamm1
    gmgmk = gam * gammk
    gmgm1 = gam * gamm1
    gm1sq = gamm1 * gamm1

    rho2 = rho * rho
    a0pq = a0 - cpcq
    t = -2.0 * wvno2

    ca[0, 0] = cpcq - 2.0 * gmgm1 * a0pq - gmgmk * xz - wvno2 * gm1sq * wy
    ca[0, 1] = (wvno2 * cpy - cqx) / rho
    ca[0, 2] = -(twgm1 * a0pq + gammk * xz + wvno2 * gamm1 * wy) / rho
    ca[0, 3] = (cpz - wvno2 * cqw) / rho
    ca[0, 4] = -(2.0 * wvno2 * a0pq + xz + wvno2 * wvno2 * wy) / rho2

    ca[1, 0] = (gmgmk * cpz - gm1sq * cqw) * rho
    ca[1, 1] = cpcq
    ca[1, 2] = gammk * cpz - gamm1 * cqw
    ca[1, 3] = -wz
    ca[1, 4] = ca[0, 3]

    ca[3, 0] = (gm1sq * cpy - gmgmk * cqx) * rho
    ca[3, 1] = -xy
    ca[3, 2] = gamm1 * cpy - gammk * cqx
    ca[3, 3] = ca[1, 1]
    ca[3, 4] = ca[0, 1]
    
    ca[4, 0] = -(2.0 * gmgmk * gm1sq * a0pq + gmgmk * gmgmk * xz + gm1sq * gm1sq * wy) * rho2
    ca[4, 1] = ca[3, 0]
    ca[4, 2] = -(gammk * gamm1 * twgm1 * a0pq + gam * gammk * gammk * xz + gamm1 * gm1sq * wy) * rho
    ca[4, 3] = ca[1, 0]
    ca[4, 4] = ca[0, 0]

    ca[2, 0] = t * ca[4, 2]
    ca[2, 1] = t * ca[3, 2]
    ca[2, 2] = a0 + 2.0 * (cpcq - ca[0, 0])
    ca[2, 3] = t * ca[1, 2]
    ca[2, 4] = t * ca[0, 2]

    return ca


@jitted
def normc(ee):
    """Normalize Haskell or Dunkin vectors."""
    t1 = 0.0
    for i in range(5):
        t1 = max(t1, numpy.abs(ee[i]))

    if t1 < 1.0e-40:
        t1 = 1.0

    for i in range(5):
        ee[i] /= t1


@jitted
def var(p, q, ra, rb, wvno, xka, xkb, dpth):
    """Find variables cosP, cosQ, sinP, sinQ..."""
    # Examine P-wave eigenfunctions
    # Checking whether c > vp, c = vp or c < vp
    pex = 0.0
    if wvno < xka:
        sinp = numpy.sin(p)
        w = sinp / ra
        x = -ra * sinp
        cosp = numpy.cos(p)
    elif wvno == xka:
        cosp = 1.0
        w = dpth
        x = 0.0
    elif wvno > xka:
        pex = p
        fac = numpy.exp(-2.0 * p) if p < 16.0 else 0.0
        cosp = (1.0 + fac) * 0.5
        sinp = (1.0 - fac) * 0.5
        w = sinp / ra
        x = ra * sinp

    # Examine S-wave eigenfunctions
    # Checking whether c > vs, c = vs or c < vs
    sex = 0.0
    if wvno < xkb:
        sinq = numpy.sin(q)
        y = sinq / rb
        z = -rb * sinq
        cosq = numpy.cos(q)
    elif wvno == xkb:
        cosq = 1.0
        y = dpth
        z = 0.0
    elif wvno > xkb:
        sex = q
        fac = numpy.exp(-2.0 * q) if q < 16.0 else 0.0
        cosq = (1.0 + fac) * 0.5
        sinq = (1.0 - fac) * 0.5
        y = sinq / rb
        z = rb * sinq

    # Form eigenfunction products for use with compound matrices
    exa = pex + sex
    a0 = numpy.exp(-exa) if exa < 60.0 else 0.0
    cpcq = cosp * cosq
    cpy = cosp * y
    cpz = cosp * z
    cqw = cosq * w
    cqx = cosq * x
    xy = x * y
    xz = x * z
    wy = w * y
    wz = w * z

    qmp = sex - pex
    fac = numpy.exp(qmp) if qmp > -40.0 else 0.0
    cosq *= fac
    y *= fac
    z *= fac

    return w, cosp, a0, cpcq, cpy, cpz, cqw, cqx, xy, xz, wy, wz


@jitted
def dltar4(wvno, omega, d, a, b, rho):
    e = numpy.zeros(5, dtype=numpy.float64)
    ee = numpy.zeros(5, dtype=numpy.float64)
    
    omega = max(omega, 1.0e-4)
    wvno2 = wvno * wvno
    xka = omega / a[-1]
    xkb = omega / b[-1]
    wvnop = wvno + xka
    wvnom = numpy.abs(wvno - xka)
    ra = numpy.sqrt(wvnop * wvnom)
    wvnop = wvno + xkb
    wvnom = numpy.abs(wvno - xkb)
    rb = numpy.sqrt(wvnop * wvnom)
    t = b[-1] / omega

    # E matrix for the bottom half-space
    gammk = 2.0 * t * t
    gam = gammk * wvno2
    gamm1 = gam - 1.0
    rho1 = rho[-1]
    e[0] = rho1 * rho1 * (gamm1 * gamm1 - gam * gammk * ra * rb)
    e[1] = -rho1 * ra
    e[2] = rho1 * (gamm1 - gammk * ra * rb)
    e[3] = rho1 * rb
    e[4] = wvno2 - ra * rb

    # Matrix multiplication from bottom layer upward
    for m in range(len(d)-2, -1, -1):
        xka = omega / a[m]
        xkb = omega / b[m]
        t = b[m] / omega
        gammk = 2.0 * t * t
        gam = gammk * wvno2
        wvnop = wvno + xka
        wvnom = numpy.abs(wvno - xka)
        ra = numpy.sqrt(wvnop * wvnom)
        wvnop = wvno + xkb
        wvnom = numpy.abs(wvno - xkb)
        rb = numpy.sqrt(wvnop * wvnom)

        dpth = d[m]
        rho1 = rho[m]
        p = ra * dpth
        q = rb * dpth
        # beta = b[m]

        # Evaluate cosP, cosQ...
        _, _, a0, cpcq, cpy, cpz, cqw, cqx, xy, xz, wy, wz = var(p, q, ra, rb, wvno, xka, xkb, dpth)

        # Evaluate Dunkin's matrix
        ca = dnka(wvno2, gam, gammk, rho1, a0, cpcq, cpy, cpz, cqw, cqx, xy, xz, wy, wz)

        for i in range(5):
            ee[i] = 0.0
            for j in range(5):
                ee[i] += e[j] * ca[j, i]

        normc(ee)
        for i in range(5):
            e[i] = ee[i]

    return e[0]


@jitted
def nevill(t, c1, c2, del1, del2, d, a, b, rho, ifunc):
    """Hybrid method for refining root once it has been bracketted."""
    x = numpy.zeros(20, dtype=numpy.float64)
    y = numpy.zeros(20, dtype=numpy.float64)

    # Initial guess
    omega = twopi / t
    c3 = 0.5 * (c1 + c2)
    del3 = dltar4(omega / c3, omega, d, a, b, rho)
    nev = 1
    nctrl = 1

    while True:
        nctrl += 1
        if nctrl >= 100:
            break

        # Make sure new estimate is inside the previous values
        # If not, perform interval halving
        if c3 < min(c1, c2) or c3 > max(c1, c2):
            nev = 0
            c3 = 0.5 * (c1 + c2)
            del3 = dltar4(omega / c3, omega, d, a, b, rho)

        s13 = del1 - del3
        s32 = del3 - del2

        # Define new bounds according to the sign of the period equation
        if numpy.sign(del3) * numpy.sign(del1) < 0.0:
            c2 = c3
            del2 = del3
        else:
            c1 = c3
            del1 = del3

        # Check for convergence
        if numpy.abs(c1 - c2) <= 1.0e-6 * c1:
            break

        # If the slopes are not the same between c1, c2 and c3
        # Do not use Neville iteration
        if numpy.sign(s13) != numpy.sign(s32):
            nev = 0

        # If the period equation differs by more than a factor of 10
        # Use interval halving to avoid poor behavior of polynomial fit
        ss1 = numpy.abs(del1)
        s1 = 0.01 * ss1
        ss2 = numpy.abs(del2)
        s2 = 0.01 * ss2
        if s1 > ss2 or s2 > ss1 or nev == 0:
            c3 = 0.5 * (c1 + c2)
            del3 = dltar4(omega / c3, omega, d, a, b, rho)
            nev = 1
            m = 1
        else:
            if nev == 2:
                x[m-1] = c3
                y[m-1] = del3
            else:
                x[0] = c1
                y[0] = del1
                x[1] = c2
                y[1] = del2
                m = 1

            # Perform Neville iteration
            flag = 1
            for kk in range(m):
                j = m - kk
                denom = y[m] - y[j]
                if numpy.abs(denom) < 1.0e-10 * numpy.abs(y[m]):
                    flag = 0
                    break
                else:
                    x[j-1] = (-y[j-1] * x[j] + y[m] * x[j-1]) / denom

            if flag:
                c3 = x[0]
                del3 = dltar4(omega / c3, omega, d, a, b, rho)
                nev = 2
                m += 1
                m = min(m, 10)
            else:
                c3 = 0.5 * (c1 + c2)
                del3 = dltar4(omega / c3, omega, d, a, b, rho)
                nev = 1
                m = 1
    
    return c3


@jitted
def getsol(t1, c1, clow, dc, cm, betmx, ifirst, del1st, d, a, b, rho, ifunc):
    """Bracket dispersion curve and then refine it."""
    # Bracket solution
    omega = twopi / t1
    del1 = dltar4(omega / c1, omega, d, a, b, rho)
    del1st = del1 if ifirst == 1 else del1st
    idir = -1.0 if ifirst != 1 and numpy.sign(del1st) * numpy.sign(del1) < 0.0 else 1.0

    # idir indicates the direction of the search for the true phase velocity from the initial estimate
    while True:
        c2 = c1 + idir * dc

        if c2 <= clow:
            idir = 1.0
            c1 = clow
        else:
            omega = twopi / t1
            del2 = dltar4(omega / c2, omega, d, a, b, rho)

            if numpy.sign(del1) != numpy.sign(del2):
                c1 = nevill(t1, c1, c2, del1, del2, d, a, b, rho, ifunc)
                iret = -1 if c1 > betmx else 1
                break

            c1 = c2
            del1 = del2

            if betmx + dc <= c1 < cm:
                iret = -1
                break

    return c1, del1st, iret


@jitted
def gtsolh(a, b):
    """Starting solution."""
    c = 0.95 * b

    for _ in range(5):
        gamma = b / a
        kappa = c / b
        k2 = kappa ** 2
        gk2 = (gamma * kappa) ** 2
        fac1 = numpy.sqrt(1.0 - gk2)
        fac2 = numpy.sqrt(1.0 - k2)
        fr = (2.0 - k2) ** 2 - 4.0 * fac1 * fac2
        frp = -4.0 * (2.0 - k2) * kappa
        frp += 4.0 * fac2 * gamma * gamma * kappa / fac1
        frp += 4.0 * fac1 * kappa / fac2
        frp /= b
        c -= fr / frp

    return c


@jitted
def srfdis(t, d, a, b, rho, mode, dc):
    """Get phase velocity dispersion curve."""
    # Initialize arrays
    kmax = len(t)
    c = numpy.zeros(kmax, dtype=numpy.float64)
    cg = numpy.zeros(kmax, dtype=numpy.float64)

    # Find the extremal velocities to assist in starting search
    betmx = -1.0e20
    betmn = 1.0e20
    for i in range(len(b)):
        if b[i] > 0.01 and b[i] < betmn:
            betmn = b[i]
            jmn = i
        elif b[i] < 0.01 and a[i] > betmn:
            betmn = a[i]
            jmn = i
        betmx = max(betmx, b[i])

    # Solid layer solve halfspace period equation
    cc = gtsolh(a[jmn], b[jmn])

    # Back off a bit to get a starting value at a lower phase velocity
    cc *= 0.9
    c1 = cc
    cm = cc

    one = 1.0e-2
    onea = 1.5
    ifunc = 2
    for iq in range(mode):
        ibeg = 0
        iend = kmax

        del1st = 0.0
        for k in range(ibeg, iend):
            # Get initial phase velocity estimate to begin search
            ifirst = int(k == ibeg)
            if ifirst and iq == 0:
                clow = cc
                c1 = cc
            elif ifirst and iq > 0:
                clow = c1
                c1 = c[ibeg] + one * dc
            elif not ifirst and iq > 0:
                clow = c[k] + one * dc
                c1 = max(c[k - 1], clow)
            elif not ifirst and iq == 0:
                clow = cm
                c1 = c[k - 1] - onea * dc

            # Bracket root and refine it
            c1, del1st, iret = getsol(
                t[k], c1, clow, dc, cm, betmx, ifirst, del1st, d, a, b, rho, ifunc
            )

            if iret == -1 and iq > 0:
                for i in range(k, kmax):
                    cg[i] = 0.0

                if iq == mode - 1:
                    return cg
                else:
                    c1 = 0.0
                    break

            c[k] = c1
            cg[k] = c[k]
            c1 = 0.0

    return cg