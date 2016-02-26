"""
Functions for more advanced calculations of quantities and properties of
quantum objects.
"""
# TODO: entanglement cross matrix, sparse ptr

from collections import OrderedDict
from itertools import product
import numpy as np
import numpy.linalg as nla
from .core import (isop, qjf, kron, ldmul,
                        eyepad, tr, trx, infer_size, eyepad)
from .gen import (sig, basis_vec, bell_state)
from .solve import (eigvals, eigsys, norm2)


def partial_transpose(p, dims=[2, 2]):
    """
    Partial transpose of state `p` with bipartition as given by `dims`.
    """
    p = qjf(p, 'op')
    p = np.array(p)\
        .reshape((*dims, *dims))  \
        .transpose([2, 1, 0, 3])  \
        .reshape((np.prod(dims), np.prod(dims)))
    return qjf(p)


def entropy(rho):
    """
    Computes the (von Neumann) entropy of positive matrix rho
    """
    l = eigvals(rho)
    l = l[l > 0.0]
    return np.sum(-l * np.log2(l))


def mutual_information(p, dims=[2, 2], sysa=0, sysb=1):
    """
    Partitions rho into dims, and finds the mutual information between the
    subsystems at indices sysa and sysb
    """
    if isop(p) or np.size(dims) > 2:  # mixed combined system
        rhoab = trx(p, dims, [sysa, sysb])
        rhoa = trx(rhoab, np.r_[dims[sysa], dims[sysb]], 0)
        rhob = trx(rhoab, np.r_[dims[sysa], dims[sysb]], 1)
        hab = entropy(rhoab)
        ha = entropy(rhoa)
        hb = entropy(rhob)
    else:  # pure combined system
        hab = 0.0
        rhoa = trx(p, dims, sysa)
        ha = entropy(rhoa)
        hb = ha
    return ha + hb - hab


def sqrtm(a):
    # returns sqrt of hermitan matrix, seems faster than scipy.linalg.sqrtm
    l, v = eigsys(a, sort=False)
    l = np.sqrt(l.astype(complex))
    return v @ ldmul(l, v.H)


def trace_norm(a):
    """
    Returns the trace norm of operator a, that is, the sum of abs eigvals.
    """
    return np.sum(np.absolute(eigvals(a, sort=False)))


def trace_distance(p, w):
    return 0.5 * trace_norm(p - w)


def negativity(rho, dims=[2, 2], sysa=0, sysb=1):
    if np.size(dims) > 2:
        rho = trx(rho, dims, [sysa, sysb])
    n = (trace_norm(partial_transpose(rho)) - 1.0) / 2.0
    return max(0.0, n)


def logarithmic_negativity(p, dims=[2, 2], sysa=0, sysb=1):
    if np.size(dims) > 2:
        p = trx(p, dims, [sysa, sysb])
        dims = [dims[sysa], dims[sysb]]
    e = np.log2(trace_norm(partial_transpose(p, dims)))
    return max(0.0, e)

logneg = logarithmic_negativity


def concurrence(p):
    if isop(p):
        p = qjf(p, 'dop')  # make sure density operator
        pt = kron(sig(2), sig(2)) @ p.conj() @ kron(sig(2), sig(2))
        l = (nla.eigvals(p @ pt).real**2)**0.25
        return max(0, 2 * np.max(l) - np.sum(l))
    else:
        p = qjf(p, 'ket')
        pt = kron(sig(2), sig(2)) @ p.conj()
        c = np.real(abs(p.H @ pt)).item(0)
        return max(0, c)


def qid(p, dims, inds, precomp_func=False, sparse_comp=True):
    p = qjf(p, 'dop')
    inds = np.array(inds, ndmin=1)
    # Construct operators
    ops_i = list([list([eyepad(sig(s), dims, ind, sparse=sparse_comp)
                        for s in (1, 2, 3)])
                  for ind in inds])

    # Define function closed over precomputed operators
    def qid_func(x):
        qds = np.zeros(np.size(inds))
        for i, ops in enumerate(ops_i):
            for op in ops:
                qds[i] += norm2(x @ op - op @ x)**2 / 3.0
        return qds

    return qid_func if precomp_func else qid_func(p)


def pauli_decomp(a, mode='p', tol=1e-3):
    """
    Decomposes an operator via the Hilbert-schmidt inner product into the
    pauli group. Can both print the decomposition or return it.

    Parameters
    ----------
        a: operator to decompose
        mode: string, include 'p' to print the decomp and/or 'c' to return dict
        tol: print operators with contirbution above tol only.

    Returns
    -------
        nds: OrderedDict of Pauli operator name and overlap with a.

    Examples
    --------
    >>> pauli_decomp( singlet(), tol=1e-2)
    II  0.25
    XX -0.25
    YY -0.25
    ZZ -0.25
    """
    a = qjf(a, 'dop')  # make sure operator
    n = int(np.log2(a.shape[0]))  # infer number of qubits

    # define generator for inner product to iterate over efficiently
    def calc_name_and_overlap(fa):
        for perm in product('IXYZ', repeat=n):
            name = "".join(perm)
            op = kron(*[sig(s, sparse=True) for s in perm]) / 2**n
            d = tr(a @ op)
            yield name, d

    nds = [nd for nd in calc_name_and_overlap(a)]
    # sort by descending overlap and turn into OrderedDict
    nds.sort(key=lambda pair: -abs(pair[1]))
    nds = OrderedDict(nds)
    # Print decomposition
    if 'p' in mode:
        for x, d in nds.items():
            if abs(d) < 0.01:
                break
            dps = int(round(0.5 - np.log10(1.001 * tol)))  # dec places to show
            print(x, '{: .{prec}f}'.format(d, prec=dps))
    # Return full calculation
    if 'c' in mode:
        return nds


def purify(rho, sparse=False):
    """
    Take state rho and purify it into a wavefunction of squared dimension.
    """
    d = rho.shape[0]
    ls, vs = eigsys(rho)
    ls = np.sqrt(ls)
    psi = np.zeros(shape=(d**2, 1), dtype=complex)
    for i, l in enumerate(ls.flat):
        psi += l * kron(vs[:, i], basis_vec(i, d, sparse=sparse))
    return qjf(psi)


def bell_fid(p):
    """
    Outputs a tuple of state p's fidelities with the four bell states
    psi- (singlet) psi+, phi-, phi+ (triplets).
    """
    op = isop(p)
    def gen_bfs():
        for b in ['psi-', 'psi+', 'phi-', 'phi+']:
            psib = bell_state(b)
            if op:
                yield tr(psib.H @ p @ psib)
            else:
                yield abs(psib.H @ p)[0, 0]**2

    return [*gen_bfs()]


def correlation(p, sysa, sysb, opa, opb, sparse=True, precomp_func=False):
    """
    Calculate the correlation between two sites given two operators.

    Parameters
    ----------
        p: state
        sysa: index of first subsystem
        sysb: index of second subsystem
        opa: operator to act on first subsystem
        opb: operator to act on second subsystem
        sparse: whether to compute with sparse operators
        precomp_func: whether to return result or single arg function closed
            over precomputed operators

    Returns
    -------
        cab: correlation, <ab> - <a><b>
    """
    sz_p = infer_size(p)
    dims = [2] * sz_p
    op = isop(p)

    opab = eyepad([opa, opb], dims, [sysa, sysb], sparse=sparse)
    opa = eyepad([opa], dims, sysa, sparse=sparse)
    opb = eyepad([opb], dims, sysb, sparse=sparse)

    if op:
        def corr(state):
            return tr(opab @ state) - tr(opa @ state) * tr(opb @ state)
    else:
        def corr(state):
            return tr(state.H @ opab @ state -
                      (state.H @ opa @ state) * (state.H @ opb @ state))

    return corr if precomp_func else corr(p)


def correlation_list(p, sysa=0, sysb=1, ss=('xx', 'yy', 'zz'),
                     sum_abs=False, precomp_func=False):
    """
    Calculate the correlation between sites for a list of operator pairs.

    Parameters
    ----------
        p: state
        sysa: index of first site
        sysb: index of second site
        ss: list of pairs specifiying pauli matrices
        sum_abs: whether to sum over the absolute values of each correlation
        precomp_func: whether to return the values or a single argument
            function closed over precomputed operators etc.

    Returns
    -------
        corrs: list of values or functions specifiying each correlation.
    """
    def gen_corr_list():
        for s1, s2 in ss:
            yield correlation(p, sysa, sysb, sig(s1), sig(s2),
                              precomp_func=precomp_func)

    if sum_abs:
        if precomp_func:
            return lambda p: sum((abs(corr(p)) for corr in gen_corr_list()))
        return sum((abs(corr) for corr in gen_corr_list()))
    return [*gen_corr_list()]


def ent_cross_matrix(p, ent_fun=concurrence, calc_self_ent=True):
    """
    Calculate the pair-wise function ent_fun  between all sites of a state.

    Parameters
    ----------
        p: state
        ent_fun: function acting on space [2, 2], notionally entanglement
        calc_self_ent: whether to calculate the function for each site
            alone, purified. If the whole state is pure then this is the
            entanglement with the whole remaining system.

    Returns
    -------
        ents: matrix of pairwise ent_fun results.
    """
    sz_p = infer_size(p)
    ents = np.empty((sz_p, sz_p))
    for i in range(sz_p):
        for j in range(i, sz_p):
            if i==j:
                if calc_self_ent:
                    rhoa = trx(p, [2]*sz_p, i)
                    psiap = purify(rhoa)
                    ent = ent_fun(psiap)
                else:
                    ent = np.nan
            else:
                rhoab = trx(p, [2]*sz_p, [i, j])
                ent = ent_fun(rhoab)
            ents[i,j] = ent
            ents[j,i] = ent
    return ents
