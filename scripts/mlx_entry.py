"""Official single-process ring initialization avoids Anaconda's incompatible MPICH.
https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.distributed.init.html
No change to LoRA implementation or optimizer. Only distributed backend selection.
"""
import os,pathlib
# Official loader honors MLX_MPI_LIBNAME. A deliberately unavailable path makes
# MPI unavailable without loading Anaconda's MPICH into this single-process job.
os.environ['MLX_MPI_LIBNAME']=str(pathlib.Path(__file__).resolve().parents[1]/'models/MPI_DISABLED_LOCAL_ONLY.dylib')
import mlx.core as mx
group=mx.distributed.init(backend='ring')
assert group.size()==1, 'This project is local single-device only'
from mlx_lm.lora import main
if __name__=='__main__':
    try:main()
    finally:print('MLX_PEAK_MEMORY_BYTES',mx.get_peak_memory(),flush=True)
