"""Trace an embedded, already-segmented sign face into closed cubic CAD paths."""
import ctypes as ct
import ctypes.util
import numpy as np
from PIL import Image
from ezdxf.path import Path
from .geometry import Mark

class Point(ct.Structure):
    _fields_=[('x',ct.c_double),('y',ct.c_double)]
class Curve(ct.Structure):
    _fields_=[('n',ct.c_int),('tag',ct.POINTER(ct.c_int)),('c',ct.POINTER(Point*3))]
class Chain(ct.Structure):
    pass
Chain._fields_=[('area',ct.c_int),('sign',ct.c_int),('curve',Curve),('next',ct.POINTER(Chain)),
                ('childlist',ct.POINTER(Chain)),('sibling',ct.POINTER(Chain)),('priv',ct.c_void_p)]
class Tracing(ct.Structure):
    _fields_=[('status',ct.c_int),('plist',ct.POINTER(Chain)),('priv',ct.c_void_p)]
class Bitmap(ct.Structure):
    _fields_=[('w',ct.c_int),('h',ct.c_int),('dy',ct.c_int),('map',ct.POINTER(ct.c_ulong))]

def read_mask(path):
    lib=ct.CDLL(ctypes.util.find_library('potrace') or 'libpotrace.so.0')
    lib.potrace_param_default.restype=ct.c_void_p
    lib.potrace_trace.argtypes=[ct.c_void_p,ct.POINTER(Bitmap)]
    lib.potrace_trace.restype=ct.POINTER(Tracing)
    lib.potrace_state_free.argtypes=[ct.POINTER(Tracing)]
    lib.potrace_param_free.argtypes=[ct.c_void_p]
    with Image.open(path) as source:
        rgba=source.convert('RGBA')
        im=Image.alpha_composite(Image.new('RGBA',source.size,'white'),rgba).convert('L')
    w,h=im.size
    bits=ct.sizeof(ct.c_ulong)*8
    stride=(w+bits-1)//bits
    mono=np.asarray(im)<128
    padded=np.pad(mono,((0,0),(0,stride*bits-w)))
    native=np.packbits(padded,axis=1).view('>u'+str(bits//8)).astype('uint'+str(bits))
    buf=(ct.c_ulong*(stride*h)).from_buffer(native)
    params=lib.potrace_param_default()
    bitmap=Bitmap(w,h,stride,buf);trace=lib.potrace_trace(params,ct.byref(bitmap))
    if not trace or trace.contents.status:raise RuntimeError('Potrace could not trace '+str(path))
    def xy(pt):return pt.x,h-pt.y
    def make_path(link):
        curve=link.contents.curve
        p=Path(xy(curve.c[curve.n-1][2]))
        for i in range(curve.n):
            c=curve.c[i]
            if curve.tag[i]==2:
                p.line_to(xy(c[1]));p.line_to(xy(c[2]))
            else:p.curve4_to(xy(c[2]),xy(c[0]),xy(c[1]))
        p.close()
        return p
    marks=[]
    try:
        node=trace.contents.plist
        while node:
            if node.contents.sign==ord('+'):
                rings=[make_path(node)]
                child=node.contents.childlist
                while child:
                    rings.append(make_path(child))
                    child=child.contents.sibling
                marks.append(Mark(rings,True,False,'TRACE-SHELL'))
            node=node.contents.next
    finally:
        lib.potrace_state_free(trace);lib.potrace_param_free(params)
    return marks,(0,0,w,h)
