"""Pin one registered metamodel CLI process to a single allowed Windows CPU."""
import ctypes
import os
import runpy
import sys

kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
process=kernel.GetCurrentProcess(); available=ctypes.c_size_t(); system=ctypes.c_size_t()
if not kernel.GetProcessAffinityMask(process,ctypes.byref(available),ctypes.byref(system)):
    raise ctypes.WinError(ctypes.get_last_error())
cores=[1<<i for i in range(ctypes.sizeof(ctypes.c_size_t)*8) if available.value & (1<<i)]
index=int(sys.argv[1])
if index<0 or index>=len(cores): raise ValueError(f'CPU index {index} not in {len(cores)} available logical CPUs')
if not kernel.SetProcessAffinityMask(process,cores[index]): raise ctypes.WinError(ctypes.get_last_error())
sys.argv=['metamodel.cli']+sys.argv[2:]
sys.path.insert(0,os.getcwd())
runpy.run_module('metamodel.cli',run_name='__main__')
