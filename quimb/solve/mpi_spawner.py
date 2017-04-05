"""Manages the spawning of mpi processes to send to the slepc solver.
"""
# TODO: don't send whole matrix? only marginal time savings but memory better.


from .slepc_solver import slepc_seigsys
from .scalapy_solver import scalapy_eigsys

import os
for var in ['QMB_NUM_MPI_WORKERS', 'MPI_UNIVERSE_SIZE', 'OMP_NUM_THREADS']:
    if var in os.environ:
        _NUM_MPI_WORKERS = int(os.environ[var])
        _NUM_MPI_WORKERS_SET = True
        break
    _NUM_MPI_WORKERS_SET = False

if not _NUM_MPI_WORKERS_SET:
    import psutil
    _NUM_MPI_WORKERS = psutil.cpu_count(logical=False)


class CachedPoolWithShutdown(object):
    """
    """

    def __init__(self, pool_fn):
        self._settings = '__UNINITIALIZED__'
        self._pool_fn = pool_fn

    def __call__(self, num_workers=None, num_threads=1):
        # convert None to default so the cache the same
        if num_workers is None:
            num_workers = _NUM_MPI_WORKERS

        # first call
        if self._settings == '__UNINITIALIZED__':
            self._pool = self._pool_fn(num_workers, num_threads)
            self._settings = (num_workers, num_threads)
        # new type of pool requested
        elif self._settings != (num_workers, num_threads):
            self._pool.shutdown()
            self._pool = self._pool_fn(num_workers, num_threads)
            self._settings = (num_workers, num_threads)
        return self._pool


@CachedPoolWithShutdown
def get_mpi_pool(num_workers=None, num_threads=1):
    """
    """
    from mpi4py.futures import MPIPoolExecutor
    return MPIPoolExecutor(num_workers, main=False, delay=1e-2,
                           env={'OMP_NUM_THREADS': str(num_threads),
                                'MPI_UNIVERSE_SIZE': '1'})


def mpi_spawn_func(fn, mat, *args,
                   num_workers=None,
                   num_threads=1,
                   mpi_pool=None,
                   **kwargs):
    """Automatically wrap a function to be executed in parallel by a
    pool of spawned mpi workers.
    """
    if num_workers is None:
        num_workers = min(_NUM_MPI_WORKERS, mat.shape[0])

    if mpi_pool is None:
        pool = get_mpi_pool(num_workers, num_threads)

    futures = [pool.submit(fn, mat, *args, **kwargs)
               for _ in range(num_workers)]
    results = (f.result() for f in futures)
    # Get master result, (not always first submitted)
    return next(r for r in results if r is not None)


# ---------------------------------- SLEPC ---------------------------------- #

def slepc_mpi_seigsys_submit_fn(*args, **kwargs):
    """
    """
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    return slepc_seigsys(*args, comm=comm, **kwargs)


def slepc_mpi_seigsys(mat, *args, num_workers=None, num_threads=1, **kwargs):
    """Automagically spawn mpi workers to do slepc eigen decomposition.
    """
    return mpi_spawn_func(slepc_mpi_seigsys_submit_fn, mat, *args,
                          num_workers=num_workers,
                          num_threads=num_threads, **kwargs)


# --------------------------------- SCALAPY --------------------------------- #

def scalapy_mpi_eigsys_submit_fn(*args, **kwargs):
    """
    """
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    return scalapy_eigsys(*args, comm=comm, **kwargs)


def scalapy_mpi_eigsys(mat, *args, **kwargs):
    """Automagically spawn mpi workers to do slepc eigen decomposition.
    """
    return mpi_spawn_func(scalapy_mpi_eigsys_submit_fn, mat, *args, **kwargs)
