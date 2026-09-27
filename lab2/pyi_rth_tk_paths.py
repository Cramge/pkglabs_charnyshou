import os
import sys
import ctypes


base = getattr(sys, "_MEIPASS", "")
if base:
    os.environ["TCL_LIBRARY"] = os.path.join(base, "_tcl_data")
    os.environ["TK_LIBRARY"] = os.path.join(base, "_tk_data")
    library = ctypes.WinDLL(os.path.join(base, "tcl86t.dll"))
    library.Tcl_CreateInterp.restype = ctypes.c_void_p
    library.Tcl_Init.argtypes = [ctypes.c_void_p]
    interpreter = library.Tcl_CreateInterp()
    library.Tcl_Init(interpreter)
