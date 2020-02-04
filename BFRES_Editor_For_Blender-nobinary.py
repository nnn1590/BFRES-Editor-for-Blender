################################################################
################################################################
####                                                        ####
####                BFRES EDITOR FOR BLENDER                ####
####                                                        ####
################################################################
####                       *CREDITS*                        ####
################################################################
####                                                        ####
####    John10v10:      Putting it all together,            ####
####                    devleopped all the blender          ####
####                    interfaces and most of the          ####
####                    BFRES encoding and decoding         ####
####                    algorithms.                         ####
####                                                        ####
####    AboodXD:        Developping the original            ####
####                    BFRES texture editing tools         ####
####                                                        ####
####    Exzap:          Reverse-engineering and             ####
####                    reprogramming the swizzle and       ####
####                    deswizzling algorithms for          ####
####                    encoding and decoding               ####
####                    textures.                           ####
####                                                        ####
####    RayKoopa:       Created the                         ####
####                    _parse_3x_10bit_signed              ####
####                    algorithm.                          ####
####                                                        ####
####    NWPlayer123:    Created the PyGecko Library         ####
####                                                        ####
####    Chadderz:       Created the TCPGecko Codehandler    ####
####                                                        ####
####    Marionumber1:   Created the TCPGecko Codehandler    ####
####                                                        ####
################################################################
################################################################
################################################################


import bpy, struct, bmesh, numpy
import os
import subprocess
import gzip
import shutil
from sys import platform

import socket  

from math import *
from mathutils import *

from random import random

from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatVectorProperty
from bpy.types import Operator

def copy(s):
    if platform == 'win32' or platform == 'cygwin':
        subprocess.Popen(['clip'], stdin=subprocess.PIPE).communicate(s.encode('UTF-8'))
    elif platform == 'linux':
        if which('xsel') is not None:
            subprocess.Popen(['xsel', '-b'], stdin=subprocess.PIPE).communicate(s.encode('UTF-8'))
        elif which('xclip') is not None:
            subprocess.Popen(['xsel', '-selection', 'clipboard'], stdin=subprocess.PIPE).communicate(s.encode('UTF-8'))
        else:
            raise Exception('xsel and xclip does not exist. Please install either one.')
    elif platform == 'darwin':
        subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE).communicate(s.encode('UTF-8'))
    else:
        raise Exception('Platform not supported')

nvcompress_windows = b''

nvcompress_license = \
"""NVIDIA Texture Tools is licensed under the MIT license.

Copyright (c) 2009-2016 Ignacio Castano
Copyright (c) 2007-2009 NVIDIA Corporation

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE."""

if platform == "win32":
    exc = gzip.decompress(nvcompress_windows)
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"nvcompress.exe", 'wb')
    f.write(exc[0x100:0xF100])
    f.close()
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"nvtt.dll", 'wb')
    f.write(exc[0xF100:0x57100])
    f.close()
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"libpng12.dll", 'wb')
    f.write(exc[0x57100:0x7E900])
    f.close()
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"jpeg62.dll", 'wb')
    f.write(exc[0x7E900:0x9DB00])
    f.close()
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"cudart32_30_14.dll", 'wb')
    f.write(exc[0x9DB00:0xE3768])
    f.close()
    del exc
    exc = gzip.decompress(b'')
    f = open(bpy.context.user_preferences.filepaths.temporary_directory+"CEMU_BFRES_FINDER.exe", 'wb')
    f.write(exc)
    f.close()
    del exc
elif platform == "darwin":
    None
elif platform == "linux":
    None
    
sock = None
tcpGecko = None
tcpGeckoCode = b''

tcpGeckoFunctions = {'findFreeSpace': b'\x0F\x80\x00\x00', 'clearMemory':b'\x0F\x80\x01\x40', 'find_bfres_headers': b'\x0F\x80\x01\xC0', 'find_bfres_headers': b'\x0F\x80\x01\xC0', 'find_bfres_headers_from_data': b'\x0F\x80\x03\x80'}

TCPBFRESLIST = []
currentDownloadedID = None

class BFRESslot():
    data = None
    
flipYZ = Matrix(((1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,0,0,1)))

class LoD():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def primitive_type(self):
        return struct.unpack(">I", self.bfres.bytes[self.offset:self.offset+0x4])[0]
    def index_format(self):
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x4:self.offset+0x8])[0]
    def count_of_points(self):
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x8:self.offset+0xC])[0]
    def index_buffer_offset(self):
        return self.offset+0x14+struct.unpack(">i", self.bfres.bytes[self.offset+0x14:self.offset+0x18])[0]
    def skip_count(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x18] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x1C:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x18:self.offset+0x1C])[0]
    def visibility_group_count(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0xC] + struct.pack(">H", set) + self.bfres.bytes[self.offset+0xE:]
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xC:self.offset+0xE])[0]
    def visibility_group_data_offset(self, i, set=None):
        offset = self.offset+0x10+struct.unpack(">i", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+i*8] + struct.pack(">i", set) + self.bfres.bytes[offset+4+i*8:]
        return struct.unpack(">i", self.bfres.bytes[offset+i*8:offset+4+i*8])[0]
    def visibility_group_data_count(self, i, set=None):
        offset = self.offset+0x10+struct.unpack(">i", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+4+i*8] + struct.pack(">i", set) + self.bfres.bytes[offset+8+i*8:]
        return struct.unpack(">i", self.bfres.bytes[offset+4+i*8:offset+8+i*8])[0]
    def primitive_type_string(self):
        pt = self.primitive_type()
        if pt == 0x01: return "GX2_PRIMITIVE_POINTS"                        #< min = 1; incr = 1
        elif pt == 0x02: return "GX2_PRIMITIVE_LINES"                       #< min = 2; incr = 2
        elif pt == 0x03: return "GX2_PRIMITIVE_LINE_STRIP"                  #< min = 2; incr = 1
        elif pt == 0x04: return "GX2_PRIMITIVE_TRIANGLES"                   #< min = 3; incr = 3
        elif pt == 0x05: return "GX2_PRIMITIVE_TRIANGLE_FAN"                #< min = 3; incr = 1
        elif pt == 0x06: return "GX2_PRIMITIVE_TRIANGLE_STRIP"              #< min = 3; incr = 1
        elif pt == 0x0a: return "GX2_PRIMITIVE_LINES_ADJACENCY"             #< min = 4; incr = 4
        elif pt == 0x0b: return "GX2_PRIMITIVE_LINE_STRIP_ADJACENCY"        #< min = 4; incr = 1
        elif pt == 0x0c: return "GX2_PRIMITIVE_TRIANGLES_ADJACENCY"         #< min = 6; incr = 6
        elif pt == 0x0d: return "GX2_PRIMITIVE_TRIANGLE_STRIP_ADJACENCY"    #< min = 6; incr = 2
        elif pt == 0x11: return "GX2_PRIMITIVE_RECTS"                       #< min = 3; incr = 3
        elif pt == 0x12: return "GX2_PRIMITIVE_LINE_LOOP"                   #< min = 2; incr = 1
        elif pt == 0x13: return "GX2_PRIMITIVE_QUADS"                       #< min = 4; incr = 4
        elif pt == 0x14: return "GX2_PRIMITIVE_QUAD_STRIP"                  #< min = 4; incr = 2
        elif pt == 0x82: return "GX2_PRIMITIVE_TESSELLATE_LINES"            #< min = 2; incr = 2
        elif pt == 0x83: return "GX2_PRIMITIVE_TESSELLATE_LINE_STRIP"       #< min = 2; incr = 1
        elif pt == 0x84: return "GX2_PRIMITIVE_TESSELLATE_TRIANGLES"        #< min = 3; incr = 3
        elif pt == 0x86: return "GX2_PRIMITIVE_TESSELLATE_TRIANGLE_STRIP"   #< min = 3; incr = 1
        elif pt == 0x93: return "GX2_PRIMITIVE_TESSELLATE_QUADS"            #< min = 4; incr = 4
        elif pt == 0x94: return "GX2_PRIMITIVE_TESSELLATE_QUAD_STRIP"       #< min = 4; incr = 2
        else: return "unknown"
    
    def index_format_string(self):
        i_f = self.index_format()
        if i_f == 0: return "GX2_INDEX_FORMAT_U16_LE"
        elif i_f == 1: return "GX2_INDEX_FORMAT_U32_LE"
        elif i_f == 4: return "GX2_INDEX_FORMAT_U16"
        elif i_f == 9: return "GX2_INDEX_FORMAT_U32"
        else: return "unknown"
    
    def get_buffer_offset(self, set=None):
        offset = self.index_buffer_offset()
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+0x14] + struct.pack(">i", set) + self.bfres.bytes[offset+0x18:]
        return offset+0x14+struct.unpack(">i", self.bfres.bytes[offset+0x14:offset+0x18])[0]
    
    def get_buffer_size(self, set=None):
        offset = self.index_buffer_offset()
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+0x4] + struct.pack(">i", set) + self.bfres.bytes[offset+0x8:]
        return struct.unpack(">i", self.bfres.bytes[offset+0x4:offset+0x8])[0]

class vtxAttribute():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def buffer_index(self):
        return self.bfres.bytes[self.offset+4]
    def format(self):
        return struct.unpack(">I", self.bfres.bytes[self.offset+8:self.offset+0xC])[0]
    def format_string(self):
        fmt = self.format()
        if fmt == 0x0000:    return "unorm_8"
        elif fmt == 0x0004:    return "unorm_8_8"
        elif fmt == 0x0007:    return "unorm_16_16"
        elif fmt == 0x000A:    return "unorm_8_8_8_8"
        elif fmt == 0x0100:    return "uint_8"
        elif fmt == 0x0104:    return "uint_8_8"
        elif fmt == 0x010A:    return "uint_8_8_8_8"
        elif fmt == 0x0200:    return "snorm_8"
        elif fmt == 0x0204:    return "snorm_8_8"
        elif fmt == 0x0207:    return "snorm_16_16"
        elif fmt == 0x020A:    return "snorm_8_8_8_8"
        elif fmt == 0x020B:    return "snorm_10_10_10_2"
        elif fmt == 0x0300:    return "sint_8"
        elif fmt == 0x0304:    return "sint_8_8"
        elif fmt == 0x030A:    return "sint_8_8_8_8"
        elif fmt == 0x0806:    return "float_32"
        elif fmt == 0x0808:    return "float_16_16"
        elif fmt == 0x080D:    return "float_32_32"
        elif fmt == 0x080F:    return "float_16_16_16_16"
        elif fmt == 0x0811:    return "float_32_32_32"
        elif fmt == 0x0813:    return "float_32_32_32_32"
        else: return "unknown"
    def buffer_offset(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x6] + struct.pack(">h", set) + self.bfres.bytes[self.offset+0x8:]
        return struct.unpack(">h", self.bfres.bytes[self.offset+0x6:self.offset+0x8])[0]

class FVTX():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    def attribute_count(self):
        return self.bfres.bytes[self.offset+4]
    def buffer_count(self):
        return self.bfres.bytes[self.offset+5]
    def section_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+6:self.offset+8])[0]
    def num_vertices(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+8] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0xC:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+8:self.offset+0xC])[0]
    def vertex_skin_count(self):
        return self.bfres.bytes[self.offset+0xC]
    def attribute_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]+0x10
    def attribute_index_group_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x14:self.offset+0x18])[0]+0x14
    def buffer_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x18:self.offset+0x1C])[0]+0x18
    
    def get_attribute_name(self, i):
        offset = self.attribute_index_group_offset()
        name_pointer_offset = offset+0x20+i*0x10
        name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
        size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
        return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
    
    def get_attribute_data(self, i):
        offset = self.attribute_index_group_offset()
        pointer_offset = offset+0x24+i*0x10
        offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
        return vtxAttribute(offset, self, self.bfres)
    
    def get_buffer_offset(self, i, set=None):
        offset = self.buffer_array_offset()
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+i*0x18+0x14] + struct.pack(">i", set) + self.bfres.bytes[offset+i*0x18+0x18:]
        return offset+i*0x18+struct.unpack(">i", self.bfres.bytes[offset+i*0x18+0x14:offset+i*0x18+0x18])[0]+0x14
    
    def get_buffer_size(self, i, set=None):
        offset = self.buffer_array_offset()
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+i*0x18+0x4] + struct.pack(">I", set) + self.bfres.bytes[offset+i*0x18+0x8:]
        return struct.unpack(">I", self.bfres.bytes[offset+i*0x18+0x4:offset+i*0x18+0x8])[0]
    
    def get_buffer_stride(self, i, set=None):
        offset = self.buffer_array_offset()
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:offset+i*0x18+0xC] + struct.pack(">H", set) + self.bfres.bytes[offset+i*0x18+0xE:]
        return struct.unpack(">H", self.bfres.bytes[offset+i*0x18+0xC:offset+i*0x18+0xE])[0]
    
class FSHP():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    def section_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xC:self.offset+0xE])[0]
    def material_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xE:self.offset+0x10])[0]
    def skeleton_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0x10:self.offset+0x12])[0]
    def vertex_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0x12:self.offset+0x14])[0]
    def skeleton_bone_skin_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0x14:self.offset+0x16])[0]
    def vertex_skin_count(self):
        return self.bfres.bytes[self.offset+0x16]
    def LoD_model_count(self):
        return self.bfres.bytes[self.offset+0x17]
    def key_shape_count(self):
        return self.bfres.bytes[self.offset+0x18]
    def vertex_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x20:self.offset+0x24])[0]+0x20
    def LoD_model_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x24:self.offset+0x28])[0]+0x24
    def skeleton_index_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x28:self.offset+0x2C])[0]+0x28

    def get_LoD_model(self, i):
        return LoD(self.LoD_model_offset()+0x1C*i, self, self.bfres)
    
    def get_bone_index(self, i):
        offset = self.skeleton_index_array_offset()
        return struct.unpack(">H", self.bfres.bytes[offset+2*i:offset+2*i+2])[0]
class texSampParam():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres 
    def index(self):
        return self.bfres.bytes[self.offset+0x14]
    
        
class matParam():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def type(self):
        return self.bfres.bytes[self.offset]
    def type_string(self):
        t = self.type()
        return  "1 bool"                    if type == 0 else\
                "2 bool"                    if type == 1 else\
                "3 bool"                    if type == 2 else\
                "4 bool"                    if type == 3 else\
                "1 signed int"              if type == 4 else\
                "2 signed int"              if type == 5 else\
                "3 signed int"              if type == 6 else\
                "4 signed int"              if type == 7 else\
                "1 unsigned int"            if type == 8 else\
                "2 unsigned int"            if type == 9 else\
                "3 unsigned int"            if type == 10 else\
                "4 unsigned int"            if type == 11 else\
                "1 float"                   if type == 12 else\
                "2 float"                   if type == 13 else\
                "3 float"                   if type == 14 else\
                "4 float"                   if type == 15 else\
                "2x2 Matrix"                if type == 16 else\
                "2x3 Matrix"                if type == 17 else\
                "2x4 Matrix"                if type == 18 else\
                "3x2 Matrix"                if type == 19 else\
                "3x3 Matrix"                if type == 20 else\
                "3x4 Matrix"                if type == 21 else\
                "4x2 Matrix"                if type == 22 else\
                "4x3 Matrix"                if type == 23 else\
                "4x4 Matrix"                if type == 24 else\
                "2D SRT"                    if type == 25 else\
                "3D SRT"                    if type == 26 else\
                "Texture SRT"               if type == 27 else\
                "Texture SRT * 3x4 Matrix"  if type == 28 else\
                "<unknown: %i>" % t
    def value_offset(self):
        return self.offset+struct.unpack(">h", self.bfres.bytes[self.offset:self.offset+2])[0]
    def value(self):
        offset = self.value_offset()
        return None

class FMAT():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    
    def texture_reference_count(self):return self.bfres.bytes[self.offset+0x10]
    
    def texture_param_count(self):return self.bfres.bytes[self.offset+0x11]

    def material_param_count(self):return self.bfres.bytes[self.offset+0x12]|(self.bfres.bytes[self.offset+0x13]<<8)
    
    def section_index(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xC:self.offset+0xE])[0]
    
    def texture_param_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x30:self.offset+0x34])[0]+0x30

    def get_texture_param_data(self, i):
        for j in range(self.texture_param_count()):
            offset = self.texture_param_array_offset()
            pointer_offset = offset+0x24+j*0x10
            offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
            bn = texSampParam(offset, self, self.bfres)
            if bn.index() == i:
                return bn
    
    def get_texture_param_name(self, i):
        for j in range(self.texture_param_count()):
            offset = self.texture_param_array_offset()
            pointer_offset = offset+0x24+j*0x10
            offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
            bn = texSampParam(offset, self, self.bfres)
            if bn.index() == i:
                offset = self.texture_param_array_offset()
                name_pointer_offset = offset+0x20+j*0x10
                name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
                size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
                return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
          
    def material_param_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x38:self.offset+0x3C])[0]+0x38

    def get_material_param_data(self, i):
        for j in range(self.material_param_count()):
            offset = self.material_param_array_offset()
            pointer_offset = offset+0x24+j*0x10
            offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
            bn = matParam(offset, self, self.bfres)
            if bn.index() == i:
                return bn
    
    def get_material_param_name(self, i):
        for j in range(self.material_param_count()):
            offset = self.material_param_array_offset()
            pointer_offset = offset+0x24+j*0x10
            offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
            bn = matParam(offset, self, self.bfres)
            if bn.index() == i:
                offset = self.texture_param_array_offset()
                name_pointer_offset = offset+0x20+j*0x10
                name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
                size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
                return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
    def material_param_data_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x3C:self.offset+0x40])[0]+0x3C
    
    def get_texture_offset(self, i):
        offset = self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x28:self.offset+0x2C])[0]+0x28+i*8
        return offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x4:self.offset+0x8])[0]+4
    def get_texture_name(self, i):
        offset = self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x28:self.offset+0x2C])[0]+0x28+i*8
        name_offset = offset+struct.unpack(">i", self.bfres.bytes[offset:offset+0x4])[0]
        size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
        return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
    
class bone():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def index(self):
        return struct.unpack(">h", self.bfres.bytes[self.offset+0x4:self.offset+0x6])[0]
    def parent_index(self):
        return struct.unpack(">h", self.bfres.bytes[self.offset+0x6:self.offset+0x8])[0]
    def smooth_matrix_index(self):
        return struct.unpack(">h", self.bfres.bytes[self.offset+0x8:self.offset+0xA])[0]
    def rigid_matrix_index(self):
        return struct.unpack(">h", self.bfres.bytes[self.offset+0xA:self.offset+0xC])[0]
    def billboard_index(self):
        return struct.unpack(">h", self.bfres.bytes[self.offset+0xC:self.offset+0xE])[0]
    def uses_euler(self):
        return (struct.unpack(">I", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]&0b00000000000000000001000000000000) != 0
    def scale_vector(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x14] + struct.pack(">fff", set[0], set[1], set[2]) + self.bfres.bytes[self.offset+0x20:]
        return struct.unpack(">3f", self.bfres.bytes[self.offset+0x14:self.offset+0x20])
    def rotation_vector(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x20] + struct.pack(">ffff", set[0], set[1], set[2], set[3]) + self.bfres.bytes[self.offset+0x30:]
        return struct.unpack(">4f", self.bfres.bytes[self.offset+0x20:self.offset+0x30])
    def translation_vector(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x30] + struct.pack(">fff", set[0], set[1], set[2]) + self.bfres.bytes[self.offset+0x3C:]
        return struct.unpack(">3f", self.bfres.bytes[self.offset+0x30:self.offset+0x3C])

class FSKL():
    def __init__(self, offset, parent, bfres):
        self.offset = offset
        self.parent = parent
        self.bfres = bfres
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    def num_bones(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0x8:self.offset+0xA])[0]
    def num_smooth_indexes(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xA:self.offset+0xC])[0]
    def num_rigid_indexes(self):
        return struct.unpack(">H", self.bfres.bytes[self.offset+0xC:self.offset+0xE])[0]
    def bone_index_group_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]+0x10
    def bone_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x14:self.offset+0x18])[0]+0x14
    def smooth_index_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x18:self.offset+0x1C])[0]+0x18
    def smooth_matrix_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x1C:self.offset+0x20])[0]+0x1C
    
    def get_bone_data(self, i, listorder = False):
        if listorder:
            offset = self.bone_index_group_offset()
            pointer_offset = offset+0x24+i*0x10
            offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
            return bone(offset, self, self.bfres)
        else:
            for j in range(self.num_bones()):
                offset = self.bone_index_group_offset()
                pointer_offset = offset+0x24+j*0x10
                offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
                bn = bone(offset, self, self.bfres)
                if bn.index() == i:
                    return bn
    
    def get_bone_name(self, i, listorder = False):
        if listorder:
            offset = self.bone_index_group_offset()
            name_pointer_offset = offset+0x20+i*0x10
            name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
            size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
            return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
        else:
            for j in range(self.num_bones()):
                offset = self.bone_index_group_offset()
                pointer_offset = offset+0x24+j*0x10
                offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
                bn = bone(offset, self, self.bfres)
                if bn.index() == i:
                    offset = self.bone_index_group_offset()
                    name_pointer_offset = offset+0x20+j*0x10
                    name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
                    size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
                    return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
            
    def get_smooth_matrix(self, i):
        offset = self.smooth_matrix_array_offset()+0x30*i
        return Matrix((struct.unpack(">4f", self.bfres.bytes[offset:offset+0x10]),(struct.unpack(">4f", self.bfres.bytes[offset+0x10:offset+0x20])),(struct.unpack(">4f", self.bfres.bytes[offset+0x20:offset+0x30])),(0,0,0,1)))
    def get_smooth_index(self, i):
        offset = self.smooth_index_array_offset()
        return struct.unpack(">H", self.bfres.bytes[offset+2*i:offset+2*i+2])[0]

class FMDL():
    def __init__(self, offset, bfres):
        self.offset = offset
        self.bfres = bfres
        self.display_info = False
        self.lod = 0
    def setup_polygon_list(self):
        self.polygons = {}
        for pi in range(self.get_polygon_count()):
            self.polygons[self.get_polygon_name(pi)] = self.get_polygon_data(pi)        
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    def skeleton_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0xC:self.offset+0x10])[0]+0xC
    def vertex_array_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]+0x10
    def poly_index_group_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x14:self.offset+0x18])[0]+0x14
    def mat_index_group_offset(self):
        return self.offset+struct.unpack(">i", self.bfres.bytes[self.offset+0x18:self.offset+0x1C])[0]+0x18
    def total_num_vertices(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x28] + struct.pack(">i", set) + self.bfres.bytes[self.offset+0x2C:]
        return struct.unpack(">i", self.bfres.bytes[self.offset+0x28:self.offset+0x2C])[0]
    
    def get_vertex_array(self):
        return FVTX(self.vertex_array_offset(), self, self.bfres)
    
    def get_polygon_count(self):
        offset = self.poly_index_group_offset()
        return struct.unpack(">I", self.bfres.bytes[offset+4:offset+8])[0]

    def get_material_count(self):
        offset = self.mat_index_group_offset()
        return struct.unpack(">I", self.bfres.bytes[offset+4:offset+8])[0]

    def get_polygon_name(self, i):
        offset = self.poly_index_group_offset()
        name_pointer_offset = offset+0x20+i*0x10
        name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
        size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
        return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")

    def get_polygon_data(self, i):
        offset = self.poly_index_group_offset()
        pointer_offset = offset+0x24+i*0x10
        offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
        return FSHP(offset, self, self.bfres)
    
    def get_material_name(self, i):
        offset = self.mat_index_group_offset()
        name_pointer_offset = offset+0x20+i*0x10
        name_offset = name_pointer_offset+struct.unpack(">i", self.bfres.bytes[name_pointer_offset:name_pointer_offset+4])[0]
        size_of_name = struct.unpack(">i", self.bfres.bytes[name_offset-4:name_offset])[0]
        return self.bfres.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")

    def get_material_data(self, i):
        offset = self.mat_index_group_offset()
        pointer_offset = offset+0x24+i*0x10
        offset = pointer_offset+struct.unpack(">i", self.bfres.bytes[pointer_offset:pointer_offset+4])[0]
        return FMAT(offset, self, self.bfres)
    
    def get_skeleton_data(self):
        return FSKL(self.skeleton_offset(), self, self.bfres)
           

class FTEX():
    def __init__(self, offset, bfres):
        self.offset = offset
        self.bfres = bfres
        self.display_info = False
    def magic(self):
        return self.bfres.bytes[self.offset:self.offset+4]
    def surface_dimension(self):return struct.unpack(">I", self.bfres.bytes[self.offset+4:self.offset+8])[0]
    def surface_dimension_string(self):
        sd = struct.unpack(">I", self.bfres.bytes[self.offset:self.offset+4])[0]
        return  "GX2_SURFACE_DIM_1D"            if sd == 0x000 else \
                "GX2_SURFACE_DIM_2D"            if sd == 0x001 else \
                "GX2_SURFACE_DIM_3D"            if sd == 0x002 else \
                "GX2_SURFACE_DIM_CUBE"          if sd == 0x003 else \
                "GX2_SURFACE_DIM_1D_ARRAY"      if sd == 0x004 else \
                "GX2_SURFACE_DIM_2D_ARRAY"      if sd == 0x005 else \
                "GX2_SURFACE_DIM_2D_MSAA"       if sd == 0x006 else \
                "GX2_SURFACE_DIM_2D_MSAA_ARRAY" if sd == 0x007 else "unknown"
    def width(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+8] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0xC:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+8:self.offset+0xC])[0]
    def height(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0xC] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x10:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0xC:self.offset+0x10])[0]
    def depth(self):
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x10:self.offset+0x14])[0]

    def num_bitmaps(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x14] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x18:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x14:self.offset+0x18])[0]
    def num_bitmaps_again(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x7C] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x80:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x7C:self.offset+0x80])[0]

    def format(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x18:self.offset+0x1C])[0]

    def format_string(self):
        fmt = self.format()
        return "GX2_SURFACE_FORMAT_INVALID"           if fmt == 0x00000000 else \
        "GX2_SURFACE_FORMAT_TC_R8_UNORM"              if fmt == 0x00000001 else \
        "GX2_SURFACE_FORMAT_TC_R8_UINT"               if fmt == 0x00000101 else \
        "GX2_SURFACE_FORMAT_TC_R8_SNORM"              if fmt == 0x00000201 else \
        "GX2_SURFACE_FORMAT_TC_R8_SINT"               if fmt == 0x00000301 else \
        "GX2_SURFACE_FORMAT_T_R4_G4_UNORM"            if fmt == 0x00000002 else \
        "GX2_SURFACE_FORMAT_TCD_R16_UNORM"            if fmt == 0x00000005 else \
        "GX2_SURFACE_FORMAT_TC_R16_UINT"              if fmt == 0x00000105 else \
        "GX2_SURFACE_FORMAT_TC_R16_SNORM"             if fmt == 0x00000205 else \
        "GX2_SURFACE_FORMAT_TC_R16_SINT"              if fmt == 0x00000305 else \
        "GX2_SURFACE_FORMAT_TC_R16_FLOAT"             if fmt == 0x00000806 else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_UNORM"           if fmt == 0x00000007 else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_UINT"            if fmt == 0x00000107 else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_SNORM"           if fmt == 0x00000207 else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_SINT"            if fmt == 0x00000307 else \
        "GX2_SURFACE_FORMAT_TCS_R5_G6_B5_UNORM"       if fmt == 0x00000008 else \
        "GX2_SURFACE_FORMAT_TC_R5_G5_B5_A1_UNORM"     if fmt == 0x0000000a else \
        "GX2_SURFACE_FORMAT_TC_R4_G4_B4_A4_UNORM"     if fmt == 0x0000000b else \
        "GX2_SURFACE_FORMAT_TC_A1_B5_G5_R5_UNORM"     if fmt == 0x0000000c else \
        "GX2_SURFACE_FORMAT_TC_R32_UINT"              if fmt == 0x0000010d else \
        "GX2_SURFACE_FORMAT_TC_R32_SINT"              if fmt == 0x0000030d else \
        "GX2_SURFACE_FORMAT_TCD_R32_FLOAT"            if fmt == 0x0000080e else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_UNORM"         if fmt == 0x0000000f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_UINT"          if fmt == 0x0000010f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_SNORM"         if fmt == 0x0000020f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_SINT"          if fmt == 0x0000030f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_FLOAT"         if fmt == 0x00000810 else \
        "GX2_SURFACE_FORMAT_D_D24_S8_UNORM"           if fmt == 0x00000011 else \
        "GX2_SURFACE_FORMAT_T_R24_UNORM_X8"           if fmt == 0x00000011 else \
        "GX2_SURFACE_FORMAT_T_X24_G8_UINT"            if fmt == 0x00000111 else \
        "GX2_SURFACE_FORMAT_D_D24_S8_FLOAT"           if fmt == 0x00000811 else \
        "GX2_SURFACE_FORMAT_TC_R11_G11_B10_FLOAT"     if fmt == 0x00000816 else \
        "GX2_SURFACE_FORMAT_TCS_R10_G10_B10_A2_UNORM" if fmt == 0x00000019 else \
        "GX2_SURFACE_FORMAT_TC_R10_G10_B10_A2_UINT"   if fmt == 0x00000119 else \
        "GX2_SURFACE_FORMAT_TC_R10_G10_B10_A2_SNORM"  if fmt == 0x00000219 else \
        "GX2_SURFACE_FORMAT_TC_R10_G10_B10_A2_SINT"   if fmt == 0x00000319 else \
        "GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_UNORM"    if fmt == 0x0000001a else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_B8_A8_UINT"      if fmt == 0x0000011a else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_B8_A8_SNORM"     if fmt == 0x0000021a else \
        "GX2_SURFACE_FORMAT_TC_R8_G8_B8_A8_SINT"      if fmt == 0x0000031a else \
        "GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_SRGB"     if fmt == 0x0000041a else \
        "GX2_SURFACE_FORMAT_TCS_A2_B10_G10_R10_UNORM" if fmt == 0x0000001b else \
        "GX2_SURFACE_FORMAT_TC_A2_B10_G10_R10_UINT"   if fmt == 0x0000011b else \
        "GX2_SURFACE_FORMAT_D_D32_FLOAT_S8_UINT_X24"  if fmt == 0x0000081c else \
        "GX2_SURFACE_FORMAT_T_R32_FLOAT_X8_X24"       if fmt == 0x0000081c else \
        "GX2_SURFACE_FORMAT_T_X32_G8_UINT_X24"        if fmt == 0x0000011c else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_UINT"          if fmt == 0x0000011d else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_SINT"          if fmt == 0x0000031d else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_FLOAT"         if fmt == 0x0000081e else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_B16_A16_UNORM" if fmt == 0x0000001f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_B16_A16_UINT"  if fmt == 0x0000011f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_B16_A16_SNORM" if fmt == 0x0000021f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_B16_A16_SINT"  if fmt == 0x0000031f else \
        "GX2_SURFACE_FORMAT_TC_R16_G16_B16_A16_FLOAT" if fmt == 0x00000820 else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_B32_A32_UINT"  if fmt == 0x00000122 else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_B32_A32_SINT"  if fmt == 0x00000322 else \
        "GX2_SURFACE_FORMAT_TC_R32_G32_B32_A32_FLOAT" if fmt == 0x00000823 else \
        "GX2_SURFACE_FORMAT_T_BC1_UNORM"              if fmt == 0x00000031 else \
        "GX2_SURFACE_FORMAT_T_BC1_SRGB"               if fmt == 0x00000431 else \
        "GX2_SURFACE_FORMAT_T_BC2_UNORM"              if fmt == 0x00000032 else \
        "GX2_SURFACE_FORMAT_T_BC2_SRGB"               if fmt == 0x00000432 else \
        "GX2_SURFACE_FORMAT_T_BC3_UNORM"              if fmt == 0x00000033 else \
        "GX2_SURFACE_FORMAT_T_BC3_SRGB"               if fmt == 0x00000433 else \
        "GX2_SURFACE_FORMAT_T_BC4_UNORM"              if fmt == 0x00000034 else \
        "GX2_SURFACE_FORMAT_T_BC4_SNORM"              if fmt == 0x00000234 else \
        "GX2_SURFACE_FORMAT_T_BC5_UNORM"              if fmt == 0x00000035 else \
        "GX2_SURFACE_FORMAT_T_BC5_SNORM"              if fmt == 0x00000235 else \
        "GX2_SURFACE_FORMAT_T_NV12_UNORM"             if fmt == 0x00000081 else \
        "GX2_SURFACE_FORMAT_LAST"                     if fmt == 0x0000083f else "unknown"
    def aa(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x1C:self.offset+0x20])[0]
    
    def data_length(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x24] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x28:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x24:self.offset+0x28])[0]

    def mipmap_data_length(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x2C] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x30:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x2C:self.offset+0x30])[0]

    def tile_mode(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x34:self.offset+0x38])[0]
    def tile_mode_string(self):
        tm = self.tile_mode()
        return    "GX2_TILE_MODE_DEFAULT"     if tm == 0x00000000 else \
        "GX2_TILE_MODE_LINEAR_SPECIAL"        if tm == 0x00000010 else \
        "GX2_TILE_MODE_LINEAR_ALIGNED"        if tm == 0x00000001 else \
        "GX2_TILE_MODE_1D_TILED_THIN1"        if tm == 0x00000002 else \
        "GX2_TILE_MODE_1D_TILED_THICK"        if tm == 0x00000003 else \
        "GX2_TILE_MODE_2D_TILED_THIN1"        if tm == 0x00000004 else \
        "GX2_TILE_MODE_2D_TILED_THIN2"        if tm == 0x00000005 else \
        "GX2_TILE_MODE_2D_TILED_THIN4"        if tm == 0x00000006 else \
        "GX2_TILE_MODE_2D_TILED_THICK"        if tm == 0x00000007 else \
        "GX2_TILE_MODE_2B_TILED_THIN1"        if tm == 0x00000008 else \
        "GX2_TILE_MODE_2B_TILED_THIN2"        if tm == 0x00000009 else \
        "GX2_TILE_MODE_2B_TILED_THIN4"        if tm == 0x0000000a else \
        "GX2_TILE_MODE_2B_TILED_THICK"        if tm == 0x0000000b else \
        "GX2_TILE_MODE_3D_TILED_THIN1"        if tm == 0x0000000c else \
        "GX2_TILE_MODE_3D_TILED_THICK"        if tm == 0x0000000d else \
        "GX2_TILE_MODE_3B_TILED_THIN1"        if tm == 0x0000000e else \
        "GX2_TILE_MODE_3B_TILED_THICK"        if tm == 0x0000000f else "unknown"
        
    def swizzle_value(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x38:self.offset+0x3C])[0]

    def alignment(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x3C:self.offset+0x40])[0]

    def pitch(self):return struct.unpack(">I", self.bfres.bytes[self.offset+0x40:self.offset+0x44])[0]

    def get_relative_mipmap_offset(self, i, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0x44+i*4] + struct.pack(">I", set) + self.bfres.bytes[self.offset+0x48+i*4:]
        return struct.unpack(">I", self.bfres.bytes[self.offset+0x44+i*4:self.offset+0x48+i*4])[0]

    def get_component_selector(self):return self.bfres.bytes[self.offset+0x88:self.offset+0x8C]

    def data_offset(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0xB0] + struct.pack(">i", set-(self.offset+0xB0)) + self.bfres.bytes[self.offset+0xB4:]
        return self.offset+0xB0+struct.unpack(">i", self.bfres.bytes[self.offset+0xB0:self.offset+0xB4])[0]

    def mipmap_offset(self, set=None):
        if set is not None:
            self.bfres.bytes = self.bfres.bytes[:self.offset+0xB4] + struct.pack(">i", set-(self.offset+0xB4)) + self.bfres.bytes[self.offset+0xB8:]
        return self.offset+0xB4+struct.unpack(">i", self.bfres.bytes[self.offset+0xB4:self.offset+0xB8])[0]

class BFRES():
    def __init__(self, filepath, data = None):
        if filepath is not None:
            f = open(filepath, "rb")
            self.bytes = f.read()
            f.close()
        else:
            self.bytes = data
        self.orig_bytes = self.bytes
        self.extra_data = []
        ei = self.size()
        while ei < len(self.bytes):
            extra_values = struct.unpack(">8I", self.bytes[ei:ei+0x20])
            pointers = []
            for pi in range(extra_values[3]):
                pointer_values = struct.unpack(">2I", self.bytes[ei+0x20+pi*8:ei+0x28+pi*8])
                pointers.append({"pointer_offset": pointer_values[0], "data_offset": pointer_values[1]})
            ei = extra_values[2]
            self.extra_data.append({"id": extra_values[0], "data": self.bytes[ei:ei+extra_values[1]], "orig_data_size": extra_values[4], "orig_data_offset": extra_values[5], "pointers": pointers})
            ei+=extra_values[1]
        self.textures = {}
        for ti in range(self.texture_index_group_count()):
            self.textures[self.get_texture_name(ti)] = self.get_texture_data(ti)
        self.models = {}
        for mi in range(self.model_index_group_count()):
            mdl = self.get_model_data(mi)
            mdl.setup_polygon_list()
            self.models[self.get_model_name(mi)] = mdl
    def apply_extra_data(self):
        self.bytes = self.bytes[:self.size()]
        for pi in range(len(self.extra_data)):
            ___data_ptr_offset = len(self.bytes) + 0x8
            self.bytes += struct.pack(">IIIIIIII", self.extra_data[pi]["id"], len(self.extra_data[pi]["data"]), 0, len(self.extra_data[pi]["pointers"]), self.extra_data[pi]["orig_data_size"], self.extra_data[pi]["orig_data_offset"], 0, 0)
            for pointer in self.extra_data[pi]["pointers"]:
                self.bytes += struct.pack(">II", pointer["pointer_offset"], pointer["data_offset"])
            while (len(self.bytes)%0x40) != 0:
                self.bytes += b'\0'
            data_offset = len(self.bytes)
            self.bytes = self.bytes[:___data_ptr_offset] + struct.pack(">I", data_offset) + self.bytes[___data_ptr_offset+4:] + self.extra_data[pi]["data"]
            for pointer in self.extra_data[pi]["pointers"]:
                self.bytes = self.bytes[:pointer["pointer_offset"]] + struct.pack(">i", pointer["data_offset"]+data_offset-pointer["pointer_offset"]) + self.bytes[pointer["pointer_offset"]+4:]
            self.extra_data[pi]["data_offset"] = data_offset
            
                
    def magic(self):
        return self.bytes[:4]
    def size(self):
        return struct.unpack(">I", self.bytes[0xC:0x10])[0]
    def model_index_group_offset(self):
        return 0x20+struct.unpack(">i", self.bytes[0x20:0x24])[0]
    def texture_index_group_offset(self):
        return 0x24+struct.unpack(">i", self.bytes[0x24:0x28])[0]
    def skeleton_animation_index_group_offset(self):
        return 0x28+struct.unpack(">i", self.bytes[0x28:0x2C])[0]
    def shader_parameters_index_group_offset(self):
        return 0x2C+struct.unpack(">i", self.bytes[0x2C:0x30])[0]
    def color_animation_index_group_offset(self):
        return 0x30+struct.unpack(">i", self.bytes[0x30:0x34])[0]
    def texture_srt_animation_index_group_offset(self):
        return 0x34+struct.unpack(">i", self.bytes[0x34:0x38])[0]
    def texture_pattern_animation_index_group_offset(self):
        return 0x38+struct.unpack(">i", self.bytes[0x38:0x3C])[0]
    def bone_visibility_animation_index_group_offset(self):
        return 0x3C+struct.unpack(">i", self.bytes[0x3C:0x40])[0]
    def material_visibility_animation_index_group_offset(self):
        return 0x40+struct.unpack(">i", self.bytes[0x40:0x44])[0]
    def shape_animation_index_group_offset(self):
        return 0x44+struct.unpack(">i", self.bytes[0x44:0x48])[0]
    def scene_animation_index_group_offset(self):
        return 0x48+struct.unpack(">i", self.bytes[0x48:0x4C])[0]
    def embedded_file_index_group_offset(self):
        return 0x4C+struct.unpack(">i", self.bytes[0x4C:0x50])[0]
    def model_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x50:0x52])[0]
    def texture_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x52:0x54])[0]
    def skeleton_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x54:0x56])[0]
    def shader_parameters_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x56:0x58])[0]
    def color_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x58:0x5A])[0]
    def texture_srt_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x5A:0x5C])[0]
    def texture_pattern_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x5C:0x5E])[0]
    def bone_visibility_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x5E:0x60])[0]
    def material_visibility_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x60:0x62])[0]
    def shape_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x62:0x64])[0]
    def scene_animation_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x64:0x66])[0]
    def embedded_file_index_group_count(self):
        return struct.unpack(">H", self.bytes[0x66:0x68])[0]
    
    def get_model_name(self, i):
        offset = self.model_index_group_offset()
        name_pointer_offset = offset+0x20+i*0x10
        name_offset = name_pointer_offset+struct.unpack(">i", self.bytes[name_pointer_offset:name_pointer_offset+4])[0]
        size_of_name = struct.unpack(">i", self.bytes[name_offset-4:name_offset])[0]
        return self.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
    
    def get_model_data(self, i):
        offset = self.model_index_group_offset()
        pointer_offset = offset+0x24+i*0x10
        offset = pointer_offset+struct.unpack(">i", self.bytes[pointer_offset:pointer_offset+4])[0]
        return FMDL(offset, self)
    
    def get_texture_name(self, i):
        offset = self.texture_index_group_offset()
        name_pointer_offset = offset+0x20+i*0x10
        name_offset = name_pointer_offset+struct.unpack(">i", self.bytes[name_pointer_offset:name_pointer_offset+4])[0]
        size_of_name = struct.unpack(">i", self.bytes[name_offset-4:name_offset])[0]
        return self.bytes[name_offset:name_offset+size_of_name].decode("UTF-8")
    
    def get_texture_data(self, i):
        offset = self.texture_index_group_offset()
        pointer_offset = offset+0x24+i*0x10
        offset = pointer_offset+struct.unpack(">i", self.bytes[pointer_offset:pointer_offset+4])[0]
        return FTEX(offset, self)
    
###############################################################################################
# _parse_3x_10bit_signed ported from io_scene_bfres/src/bfres_fmdl.py by Github user RayKoopa #
###############################################################################################
def _parse_3x_10bit_signed(buffer, offset):
            integer = struct.unpack(">I", buffer[offset:offset + 4])[0]
            # 8-bit values are aligned in 'integer' as follows:
            #   Bit: 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32
            # Value:  0  1  x  x  x  x  x  x  x  x  0  1  y  y  y  y  y  y  y  y  0  1  z  z  z  z  z  z  z  z  0  0
            # Those are then divided by 511 to retrieve the decimal value.
            x = (((((integer & 0x3FC00000) >> 22) / 511)*2+0.5)%1)*2-1
            y = (((((integer & 0x000FF000) >> 12) / 511)*2+0.5)%1)*2-1
            z = (((((integer & 0x000003FC) >> 2) / 511)*2+0.5)%1)*2-1
            return x, y, z
def _encode_3x_10bit_signed(x,y,z):
            outX = (int((((((x+1)/2))-0.5)/2)*511) << 22) & 0x3FC00000
            outY = (int((((((y+1)/2))-0.5)/2)*511) << 12) & 0x000FF000
            outZ = (int((((((z+1)/2))-0.5)/2)*511) << 2) & 0x000003FC
            return struct.pack(">I", outX|outY|outZ)

def matrix_from_transform(pos, rot, scale):
    return Matrix.Translation(pos) * rot.to_matrix().to_4x4() * Matrix(((scale[0],0,0,0),(0,scale[1],0,0),(0,0,scale[2],0),(0,0,0,1)))

def flipMtx(mtx):
    return Matrix((\
    (mtx[0][0],mtx[1][0],mtx[2][0],mtx[3][0]),\
    (mtx[0][1],mtx[1][1],mtx[2][1],mtx[3][1]),\
    (mtx[0][2],mtx[1][2],mtx[2][2],mtx[3][2]),\
    (mtx[0][3],mtx[1][3],mtx[2][3],mtx[3][3])\
    ))
def average(floats, weights):
    tw = 0
    for w in weights:
        tw+=w
    ta = 0
    for i in range(len(floats)):
        ta += floats[i] * (weights[i]/tw)
    return ta
def averageMtx(mtxs, weights):
    return Matrix(\
(\
(average([m[0][0] for m in mtxs], weights),average([m[0][1] for m in mtxs], weights),average([m[0][2] for m in mtxs], weights),average([m[0][3] for m in mtxs], weights)),\
(average([m[1][0] for m in mtxs], weights),average([m[1][1] for m in mtxs], weights),average([m[1][2] for m in mtxs], weights),average([m[1][3] for m in mtxs], weights)),\
(average([m[2][0] for m in mtxs], weights),average([m[2][1] for m in mtxs], weights),average([m[2][2] for m in mtxs], weights),average([m[2][3] for m in mtxs], weights)),\
(average([m[3][0] for m in mtxs], weights),average([m[3][1] for m in mtxs], weights),average([m[3][2] for m in mtxs], weights),average([m[3][3] for m in mtxs], weights)),\
)\
)
def writeTextureBlock(pixels, block, tx, ty, width):
    for y in range(4):
        for x in range(4):
            if (tx*4)+x < width:
                if (((ty*4)+y)*width+((tx*4)+x))*4+4 <= len(pixels):
                    pixels[(((ty*4)+y)*width+((tx*4)+x))*4+0] = block[(y*4+x)*4+0]
                    pixels[(((ty*4)+y)*width+((tx*4)+x))*4+1] = block[(y*4+x)*4+1]
                    pixels[(((ty*4)+y)*width+((tx*4)+x))*4+2] = block[(y*4+x)*4+2]
                    pixels[(((ty*4)+y)*width+((tx*4)+x))*4+3] = block[(y*4+x)*4+3]
def writePixel(pixels, pixel, x, y, width):
    if x < width:
        if ((y*width+x)*4+4) <= len(pixels):
            pixels[(y*width+x)*4+0] = pixel[0]
            pixels[(y*width+x)*4+1] = pixel[1]
            pixels[(y*width+x)*4+2] = pixel[2]
            pixels[(y*width+x)*4+3] = pixel[3]
def decode_rgb565(bits):
    r = (bits&0xF800)>>11
    g = (bits&0x7E0)>>5
    b = bits&0x1F
    return (r/31.0,g/63.0,b/31.0)
def encode_rgb565(r,g,b):
   return (int(round(r*31))&0x1F)|((int(round(g*63))&0x3F) << 5)|((int(round(b*31))&0x1F) << 11)
def lerp_color(c1, c2, t):
    return (c1[0]+(c2[0]-c1[0])*t,c1[1]+(c2[1]-c1[1])*t,c1[2]+(c2[2]-c1[2])*t)
def flipY(pixels, width):
    num_pixels = len(pixels)//4
    height = num_pixels//width
    out = []
    for i in range(height-1, -1, -1):
        out += pixels[(width*4)*i:(width*4)*(i+1)]
    return out
def crop(pixels, current_width, width, height):
    out = []
    for i in range(height):
        out += pixels[((current_width)*4)*i:((current_width)*4)*i+(width*4)]
    return out

############################################
# addrlib python file by AboodXD and Exzap #
############################################

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# addrlib.py
# A Python Address Library for Wii U textures.


BCn_formats = [
    0x31, 0x431, 0x32, 0x432,
    0x33, 0x433, 0x34, 0x234,
    0x35, 0x235,
]


def swizzleSurf(width, height, height_, format_, tileMode, swizzle_,
                pitch, bitsPerPixel, data, swizzle):

    bytesPerPixel = bitsPerPixel // 8
    result = bytearray(len(data))

    if format_ in BCn_formats:
        width = (width + 3) // 4
        height = (height + 3) // 4

    for y in range(height):
        for x in range(width):
            pipeSwizzle = (swizzle_ >> 8) & 1
            bankSwizzle = (swizzle_ >> 9) & 3

            if tileMode in [0, 1]:
                pos = computeSurfaceAddrFromCoordLinear(x, y, bitsPerPixel, pitch)

            elif tileMode in [2, 3]:
                pos = computeSurfaceAddrFromCoordMicroTiled(x, y, bitsPerPixel, pitch, tileMode)

            else:
                pos = computeSurfaceAddrFromCoordMacroTiled(x, y, bitsPerPixel, pitch, height_, tileMode,
                                                            pipeSwizzle, bankSwizzle)

            pos_ = (y * width + x) * bytesPerPixel

            if pos_ + bytesPerPixel <= len(data) and pos + bytesPerPixel <= len(data):
                if swizzle == 0:
                    result[pos_:pos_ + bytesPerPixel] = data[pos:pos + bytesPerPixel]

                else:
                    result[pos:pos + bytesPerPixel] = data[pos_:pos_ + bytesPerPixel]

    return bytes(result)


def deswizzle(width, height, height_, format_, tileMode, swizzle_,
              pitch, bpp, data):

    return swizzleSurf(width, height, height_, format_, tileMode, swizzle_, pitch, bpp, data, 0)


def swizzle(width, height, height_, format_, tileMode, swizzle_,
            pitch, bpp, data):

    return swizzleSurf(width, height, height_, format_, tileMode, swizzle_, pitch, bpp, data, 1)


m_banks = 4
m_banksBitcount = 2
m_pipes = 2
m_pipesBitcount = 1
m_pipeInterleaveBytes = 256
m_pipeInterleaveBytesBitcount = 8
m_rowSize = 2048
m_swapSize = 256
m_splitSize = 2048

m_chipFamily = 2

MicroTilePixels = 64

formatHwInfo = [
    0x00, 0x00, 0x00, 0x01, 0x08, 0x03, 0x00, 0x01, 0x08, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x01, 0x10, 0x07, 0x00, 0x00, 0x10, 0x03, 0x00, 0x01, 0x10, 0x03, 0x00, 0x01,
    0x10, 0x0B, 0x00, 0x01, 0x10, 0x01, 0x00, 0x01, 0x10, 0x03, 0x00, 0x01, 0x10, 0x03, 0x00, 0x01,
    0x10, 0x03, 0x00, 0x01, 0x20, 0x03, 0x00, 0x00, 0x20, 0x07, 0x00, 0x00, 0x20, 0x03, 0x00, 0x00,
    0x20, 0x03, 0x00, 0x01, 0x20, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x20, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x20, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x01, 0x20, 0x0B, 0x00, 0x01, 0x20, 0x0B, 0x00, 0x01, 0x20, 0x0B, 0x00, 0x01,
    0x40, 0x05, 0x00, 0x00, 0x40, 0x03, 0x00, 0x00, 0x40, 0x03, 0x00, 0x00, 0x40, 0x03, 0x00, 0x00,
    0x40, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x80, 0x03, 0x00, 0x00, 0x80, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x10, 0x01, 0x00, 0x00,
    0x10, 0x01, 0x00, 0x00, 0x20, 0x01, 0x00, 0x00, 0x20, 0x01, 0x00, 0x00, 0x20, 0x01, 0x00, 0x00,
    0x00, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x60, 0x01, 0x00, 0x00,
    0x60, 0x01, 0x00, 0x00, 0x40, 0x01, 0x00, 0x01, 0x80, 0x01, 0x00, 0x01, 0x80, 0x01, 0x00, 0x01,
    0x40, 0x01, 0x00, 0x01, 0x80, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]


def surfaceGetBitsPerPixel(surfaceFormat):
    hwFormat = surfaceFormat & 0x3F
    bpp = formatHwInfo[hwFormat * 4]

    return bpp


def computeSurfaceThickness(tileMode):
    thickness = 1

    if tileMode in [3, 7, 11, 13, 15]:
        thickness = 4

    elif tileMode in [16, 17]:
        thickness = 8

    return thickness


def computePixelIndexWithinMicroTile(x, y, bpp, tileMode):
    z = 0
    pixelBit6 = 0
    pixelBit7 = 0
    pixelBit8 = 0
    thickness = computeSurfaceThickness(tileMode)

    if bpp == 0x08:
        pixelBit0 = x & 1
        pixelBit1 = (x & 2) >> 1
        pixelBit2 = (x & 4) >> 2
        pixelBit3 = (y & 2) >> 1
        pixelBit4 = y & 1
        pixelBit5 = (y & 4) >> 2

    elif bpp == 0x10:
        pixelBit0 = x & 1
        pixelBit1 = (x & 2) >> 1
        pixelBit2 = (x & 4) >> 2
        pixelBit3 = y & 1
        pixelBit4 = (y & 2) >> 1
        pixelBit5 = (y & 4) >> 2

    elif bpp in [0x20, 0x60]:
        pixelBit0 = x & 1
        pixelBit1 = (x & 2) >> 1
        pixelBit2 = y & 1
        pixelBit3 = (x & 4) >> 2
        pixelBit4 = (y & 2) >> 1
        pixelBit5 = (y & 4) >> 2

    elif bpp == 0x40:
        pixelBit0 = x & 1
        pixelBit1 = y & 1
        pixelBit2 = (x & 2) >> 1
        pixelBit3 = (x & 4) >> 2
        pixelBit4 = (y & 2) >> 1
        pixelBit5 = (y & 4) >> 2

    elif bpp == 0x80:
        pixelBit0 = y & 1
        pixelBit1 = x & 1
        pixelBit2 = (x & 2) >> 1
        pixelBit3 = (x & 4) >> 2
        pixelBit4 = (y & 2) >> 1
        pixelBit5 = (y & 4) >> 2

    else:
        pixelBit0 = x & 1
        pixelBit1 = (x & 2) >> 1
        pixelBit2 = y & 1
        pixelBit3 = (x & 4) >> 2
        pixelBit4 = (y & 2) >> 1
        pixelBit5 = (y & 4) >> 2

    if thickness > 1:
        pixelBit6 = z & 1
        pixelBit7 = (z & 2) >> 1

    if thickness == 8:
        pixelBit8 = (z & 4) >> 2

    return ((pixelBit8 << 8) | (pixelBit7 << 7) | (pixelBit6 << 6) |
            32 * pixelBit5 | 16 * pixelBit4 | 8 * pixelBit3 |
            4 * pixelBit2 | pixelBit0 | 2 * pixelBit1)


def computePipeFromCoordWoRotation(x, y):
    # hardcoded to assume 2 pipes
    return ((y >> 3) ^ (x >> 3)) & 1


def computeBankFromCoordWoRotation(x, y):
    numPipes = m_pipes
    numBanks = m_banks
    bank = 0

    if numBanks == 4:
        bankBit0 = ((y // (16 * numPipes)) ^ (x >> 3)) & 1
        bank = bankBit0 | 2 * (((y // (8 * numPipes)) ^ (x >> 4)) & 1)

    elif numBanks == 8:
        bankBit0a = ((y // (32 * numPipes)) ^ (x >> 3)) & 1
        bank = (bankBit0a | 2 * (((y // (32 * numPipes)) ^ (y // (16 * numPipes) ^ (x >> 4))) & 1) |
                4 * (((y // (8 * numPipes)) ^ (x >> 5)) & 1))

    return bank


def isThickMacroTiled(tileMode):
    thickMacroTiled = 0

    if tileMode in [7, 11, 13, 15]:
        thickMacroTiled = 1

    return thickMacroTiled


def isBankSwappedTileMode(tileMode):
    bankSwapped = 0

    if tileMode in [8, 9, 10, 11, 14, 15]:
        bankSwapped = 1

    return bankSwapped


def computeMacroTileAspectRatio(tileMode):
    ratio = 1

    if tileMode in [8, 12, 14]:
        ratio = 1

    elif tileMode in [5, 9]:
        ratio = 2

    elif tileMode in [6, 10]:
        ratio = 4

    return ratio


def computeSurfaceBankSwappedWidth(tileMode, bpp, pitch, numSamples=1):
    if isBankSwappedTileMode(tileMode) == 0:
        return 0

    numBanks = m_banks
    numPipes = m_pipes
    swapSize = m_swapSize
    rowSize = m_rowSize
    splitSize = m_splitSize
    groupSize = m_pipeInterleaveBytesBitcount
    bytesPerSample = 8 * bpp

    if bytesPerSample != 0:
        samplesPerTile = splitSize // bytesPerSample
        slicesPerTile = max(1, numSamples // samplesPerTile)
    else:
        slicesPerTile = 1

    if isThickMacroTiled(tileMode) != 0:
        numSamples = 4

    bytesPerTileSlice = numSamples * bytesPerSample // slicesPerTile

    factor = computeMacroTileAspectRatio(tileMode)
    swapTiles = max(1, (swapSize >> 1) // bpp)

    swapWidth = swapTiles * 8 * numBanks
    heightBytes = numSamples * factor * numPipes * bpp // slicesPerTile
    swapMax = numPipes * numBanks * rowSize // heightBytes
    swapMin = groupSize * 8 * numBanks // bytesPerTileSlice

    bankSwapWidth = min(swapMax, max(swapMin, swapWidth))

    while bankSwapWidth >= 2 * pitch:
        bankSwapWidth >>= 1

    return bankSwapWidth


def computeSurfaceAddrFromCoordLinear(x, y, bpp, pitch):
    rowOffset = y * pitch
    pixOffset = x

    addr = (rowOffset + pixOffset) * bpp
    addr //= 8

    return addr


def computeSurfaceAddrFromCoordMicroTiled(x, y, bpp, pitch, tileMode):
    microTileThickness = 1

    if tileMode == 3:
        microTileThickness = 4

    microTileBytes = (MicroTilePixels * microTileThickness * bpp + 7) // 8
    microTilesPerRow = pitch >> 3
    microTileIndexX = x >> 3
    microTileIndexY = y >> 3

    microTileOffset = microTileBytes * (microTileIndexX + microTileIndexY * microTilesPerRow)

    pixelIndex = computePixelIndexWithinMicroTile(x, y, bpp, tileMode)

    pixelOffset = bpp * pixelIndex
    pixelOffset >>= 3

    return pixelOffset + microTileOffset


bankSwapOrder = [0, 1, 3, 2, 6, 7, 5, 4, 0, 0]


def computeSurfaceAddrFromCoordMacroTiled(x, y, bpp, pitch, height,
                                          tileMode, pipeSwizzle,
                                          bankSwizzle):

    numPipes = m_pipes
    numBanks = m_banks
    numGroupBits = m_pipeInterleaveBytesBitcount
    numPipeBits = m_pipesBitcount
    numBankBits = m_banksBitcount

    microTileThickness = computeSurfaceThickness(tileMode)

    microTileBits = bpp * (microTileThickness * MicroTilePixels)
    microTileBytes = (microTileBits + 7) // 8

    pixelIndex = computePixelIndexWithinMicroTile(x, y, bpp, tileMode)

    pixelOffset = bpp * pixelIndex

    elemOffset = pixelOffset

    bytesPerSample = microTileBytes

    if microTileBytes <= m_splitSize:
        numSamples = 1
        sampleSlice = 0

    else:
        samplesPerSlice = m_splitSize // bytesPerSample
        numSampleSplits = max(1, 1 // samplesPerSlice)
        numSamples = samplesPerSlice
        sampleSlice = elemOffset // (microTileBits // numSampleSplits)
        elemOffset %= microTileBits // numSampleSplits

    elemOffset += 7
    elemOffset //= 8

    pipe = computePipeFromCoordWoRotation(x, y)
    bank = computeBankFromCoordWoRotation(x, y)

    bankPipe = pipe + numPipes * bank

    swizzle_ = pipeSwizzle + numPipes * bankSwizzle

    bankPipe ^= numPipes * sampleSlice * ((numBanks >> 1) + 1) ^ swizzle_
    bankPipe %= numPipes * numBanks
    pipe = bankPipe % numPipes
    bank = bankPipe // numPipes

    sliceBytes = (height * pitch * microTileThickness * bpp * numSamples + 7) // 8
    sliceOffset = sliceBytes * (sampleSlice // microTileThickness)

    macroTilePitch = 8 * m_banks
    macroTileHeight = 8 * m_pipes

    if tileMode in [5, 9]:  # GX2_TILE_MODE_2D_TILED_THIN2 and GX2_TILE_MODE_2B_TILED_THIN2
        macroTilePitch >>= 1
        macroTileHeight *= 2

    elif tileMode in [6, 10]:  # GX2_TILE_MODE_2D_TILED_THIN4 and GX2_TILE_MODE_2B_TILED_THIN4
        macroTilePitch >>= 2
        macroTileHeight *= 4

    macroTilesPerRow = pitch // macroTilePitch
    macroTileBytes = (numSamples * microTileThickness * bpp * macroTileHeight
                      * macroTilePitch + 7) // 8
    macroTileIndexX = x // macroTilePitch
    macroTileIndexY = y // macroTileHeight
    macroTileOffset = (macroTileIndexX + macroTilesPerRow * macroTileIndexY) * macroTileBytes

    if tileMode in [8, 9, 10, 11, 14, 15]:
        bankSwapWidth = computeSurfaceBankSwappedWidth(tileMode, bpp, pitch)
        swapIndex = macroTilePitch * macroTileIndexX // bankSwapWidth
        bank ^= bankSwapOrder[swapIndex & (m_banks - 1)]

    groupMask = ((1 << numGroupBits) - 1)

    numSwizzleBits = (numBankBits + numPipeBits)

    totalOffset = (elemOffset + ((macroTileOffset + sliceOffset) >> numSwizzleBits))

    offsetHigh = (totalOffset & ~groupMask) << numSwizzleBits
    offsetLow = groupMask & totalOffset

    pipeBits = pipe << numGroupBits
    bankBits = bank << (numPipeBits + numGroupBits)

    return bankBits | pipeBits | offsetLow | offsetHigh


ADDR_OK = 0

expPitch = 0
expHeight = 0
expNumSlices = 0

m_configFlags = 4


class Flags:
    def __init__(self):
        self.value = 0


class tileInfo:
    def __init__(self):
        self.banks = 0
        self.bankWidth = 0
        self.bankHeight = 0
        self.macroAspectRatio = 0
        self.tileSplitBytes = 0
        self.pipeConfig = 0


class surfaceIn:
    def __init__(self):
        self.size = 0
        self.tileMode = 0
        self.format = 0
        self.bpp = 0
        self.numSamples = 0
        self.width = 0
        self.height = 0
        self.numSlices = 0
        self.slice = 0
        self.mipLevel = 0
        self.flags = Flags()
        self.numFrags = 0
        self.pTileInfo = tileInfo()
        self.tileIndex = 0


class surfaceOut:
    def __init__(self):
        self.size = 0
        self.pitch = 0
        self.height = 0
        self.depth = 0
        self.surfSize = 0
        self.tileMode = 0
        self.baseAlign = 0
        self.pitchAlign = 0
        self.heightAlign = 0
        self.depthAlign = 0
        self.bpp = 0
        self.pixelPitch = 0
        self.pixelHeight = 0
        self.pixelBits = 0
        self.sliceSize = 0
        self.pitchTileMax = 0
        self.heightTileMax = 0
        self.sliceTileMax = 0
        self.pTileInfo = tileInfo()
        self.tileType = 0
        self.tileIndex = 0


pIn = surfaceIn()
pOut = surfaceOut()


def getFillSizeFieldsFlags():
    return (m_configFlags >> 6) & 1


def getSliceComputingFlags():
    return (m_configFlags >> 4) & 3


def powTwoAlign(x, align):
    return ~(align - 1) & (x + align - 1)


def nextPow2(dim):
    newDim = 1
    if dim <= 0x7FFFFFFF:
        while newDim < dim:
            newDim *= 2

    else:
        newDim = 2147483648

    return newDim


def useTileIndex(index):
    if (m_configFlags >> 7) & 1 and index != -1:
        return 1

    else:
        return 0


def getBitsPerPixel(format_):
    expandY = 1
    elemMode = 3

    if format_ == 1:
        bpp = 8
        expandX = 1

    elif format_ in [5, 6, 7, 8, 9, 10, 11]:
        bpp = 16
        expandX = 1

    elif format_ == 39:
        elemMode = 7
        bpp = 16
        expandX = 1

    elif format_ == 40:
        elemMode = 8
        bpp = 16
        expandX = 1

    elif format_ in [13, 14, 15, 16, 19, 20, 21, 23, 25, 26]:
        bpp = 32
        expandX = 1

    elif format_ in [29, 30, 31, 32, 62]:
        bpp = 64
        expandX = 1

    elif format_ in [34, 35]:
        bpp = 128
        expandX = 1

    elif format_ == 0:
        bpp = 0
        expandX = 1

    elif format_ == 38:
        elemMode = 6
        bpp = 1
        expandX = 8

    elif format_ == 37:
        elemMode = 5
        bpp = 1
        expandX = 8

    elif format_ in [2, 3]:
        bpp = 8
        expandX = 1

    elif format_ == 12:
        bpp = 16
        expandX = 1

    elif format_ in [17, 18, 22, 24, 27, 41, 42, 43]:
        bpp = 32
        expandX = 1

    elif format_ == 28:
        bpp = 64
        expandX = 1

    elif format_ == 44:
        elemMode = 4
        bpp = 24
        expandX = 3

    elif format_ in [45, 46]:
        elemMode = 4
        bpp = 48
        expandX = 3

    elif format_ in [47, 48]:
        elemMode = 4
        bpp = 96
        expandX = 3

    elif format_ == 49:
        elemMode = 9
        expandY = 4
        bpp = 64
        expandX = 4

    elif format_ == 52:
        elemMode = 12
        expandY = 4
        bpp = 64
        expandX = 4

    elif format_ == 50:
        elemMode = 10
        expandY = 4
        bpp = 128
        expandX = 4

    elif format_ == 51:
        elemMode = 11
        expandY = 4
        bpp = 128
        expandX = 4

    elif format_ in [53, 54, 55]:
        elemMode = 13
        expandY = 4
        bpp = 128
        expandX = 4

    else:
        bpp = 0
        expandX = 1

    return bpp, expandX, expandY, elemMode


def adjustSurfaceInfo(elemMode, expandX, expandY, pBpp, pWidth, pHeight):
    bBCnFormat = 0

    if pBpp:
        bpp = pBpp

        if elemMode == 4:
            packedBits = bpp // expandX // expandY

        elif elemMode in [5, 6]:
            packedBits = expandY * expandX * bpp

        elif elemMode in [7, 8]:
            packedBits = pBpp

        elif elemMode in [9, 12]:
            packedBits = 64
            bBCnFormat = 1

        elif elemMode in [10, 11, 13]:
            bBCnFormat = 1
            packedBits = 128

        elif elemMode in [0, 1, 2, 3]:
            packedBits = pBpp

        else:
            packedBits = pBpp

        pIn.bpp = packedBits

    if pWidth:
        if pHeight:
            width = pWidth
            height = pHeight

            if expandX > 1 or expandY > 1:
                if elemMode == 4:
                    widtha = expandX * width
                    heighta = expandY * height

                elif bBCnFormat:
                    widtha = width // expandX
                    heighta = height // expandY

                else:
                    widtha = (width + expandX - 1) // expandX
                    heighta = (height + expandY - 1) // expandY

                pIn.width = max(1, widtha)
                pIn.height = max(1, heighta)

    return packedBits


def hwlComputeMipLevel():
    handled = 0

    if 49 <= pIn.format <= 55:
        if pIn.mipLevel:
            width = pIn.width
            height = pIn.height
            slices = pIn.numSlices

            if (pIn.flags.value >> 12) & 1:
                widtha = width >> pIn.mipLevel
                heighta = height >> pIn.mipLevel

                if not ((pIn.flags.value >> 4) & 1):
                    slices >>= pIn.mipLevel

                width = max(1, widtha)
                height = max(1, heighta)
                slices = max(1, slices)

            pIn.width = nextPow2(width)
            pIn.height = nextPow2(height)
            pIn.numSlices = slices

        handled = 1

    return handled


def computeMipLevel():
    slices = 0
    height = 0
    width = 0
    hwlHandled = 0

    if 49 <= pIn.format <= 55 and (not pIn.mipLevel or ((pIn.flags.value >> 12) & 1)):
        pIn.width = powTwoAlign(pIn.width, 4)
        pIn.height = powTwoAlign(pIn.height, 4)

    hwlHandled = hwlComputeMipLevel()
    if not hwlHandled and pIn.mipLevel and ((pIn.flags.value >> 12) & 1):
        width = pIn.width
        height = pIn.height
        slices = pIn.numSlices
        width >>= pIn.mipLevel
        height >>= pIn.mipLevel

        if not ((pIn.flags.value >> 4) & 1):
            slices >>= pIn.mipLevel

        width = max(1, width)
        height = max(1, height)
        slices = max(1, slices)

        if pIn.format not in [47, 48]:
            width = nextPow2(width)
            height = nextPow2(height)
            slices = nextPow2(slices)

        pIn.width = width
        pIn.height = height
        pIn.numSlices = slices


def convertToNonBankSwappedMode(tileMode):
    if tileMode == 8:
        expTileMode = 4

    elif tileMode == 9:
        expTileMode = 5

    elif tileMode == 10:
        expTileMode = 6

    elif tileMode == 11:
        expTileMode = 7

    elif tileMode == 14:
        expTileMode = 12

    elif tileMode == 15:
        expTileMode = 13

    else:
        expTileMode = tileMode

    return expTileMode


def computeSurfaceTileSlices(tileMode, bpp, numSamples):
    bytePerSample = ((bpp << 6) + 7) >> 3
    tileSlices = 1

    if computeSurfaceThickness(tileMode) > 1:
        numSamples = 4

    if bytePerSample:
        samplePerTile = m_splitSize // bytePerSample
        if samplePerTile:
            tileSlices = max(1, numSamples // samplePerTile)

    return tileSlices


def computeSurfaceRotationFromTileMode(tileMode):
    pipes = m_pipes
    result = 0

    if tileMode in [4, 5, 6, 7, 8, 9, 10, 11]:
        result = pipes * ((m_banks >> 1) - 1)

    elif tileMode in [12, 13, 14, 15]:
        result = 1

    return result


def computeSurfaceMipLevelTileMode(baseTileMode, bpp, level, width, height, numSlices, numSamples, isDepth, noRecursive):
    expTileMode = baseTileMode
    numPipes = m_pipes
    numBanks = m_banks
    groupBytes = m_pipeInterleaveBytes
    tileSlices = computeSurfaceTileSlices(baseTileMode, bpp, numSamples)

    if baseTileMode == 5:
        if 2 * m_pipeInterleaveBytes > m_splitSize:
            expTileMode = 4

    elif baseTileMode == 6:
        if 4 * m_pipeInterleaveBytes > m_splitSize:
            expTileMode = 5

    elif baseTileMode == 7:
        if numSamples > 1 or tileSlices > 1 or isDepth:
            expTileMode = 4

    elif baseTileMode == 13:
        if numSamples > 1 or tileSlices > 1 or isDepth:
            expTileMode = 12

    elif baseTileMode == 9:
        if 2 * m_pipeInterleaveBytes > m_splitSize:
            expTileMode = 8

    elif baseTileMode == 10:
        if 4 * m_pipeInterleaveBytes > m_splitSize:
            expTileMode = 9

    elif baseTileMode == 11:
        if numSamples > 1 or tileSlices > 1 or isDepth:
            expTileMode = 8

    elif baseTileMode == 15:
        if numSamples > 1 or tileSlices > 1 or isDepth:
            expTileMode = 14

    elif baseTileMode == 2:
        if numSamples > 1 and ((m_configFlags >> 2) & 1):
            expTileMode = 4

    elif baseTileMode == 3:
        if numSamples > 1 or isDepth:
            expTileMode = 2

        if numSamples in [2, 4]:
            expTileMode = 7

    else:
        expTileMode = baseTileMode

    rotation = computeSurfaceRotationFromTileMode(expTileMode)
    if not (rotation % m_pipes):
        if expTileMode == 12:
            expTileMode = 4

        if expTileMode == 14:
            expTileMode = 8

        if expTileMode == 13:
            expTileMode = 7

        if expTileMode == 15:
            expTileMode = 11

    if noRecursive:
        result = expTileMode

    else:
        if bpp in [24, 48, 96]:
            bpp //= 3

        widtha = nextPow2(width)
        heighta = nextPow2(height)
        numSlicesa = nextPow2(numSlices)

        if level:
            expTileMode = convertToNonBankSwappedMode(expTileMode)
            thickness = computeSurfaceThickness(expTileMode)
            microTileBytes = (numSamples * bpp * (thickness << 6) + 7) >> 3

            if microTileBytes >= groupBytes:
                v13 = 1

            else:
                v13 = groupBytes // microTileBytes

            widthAlignFactor = v13
            macroTileWidth = 8 * numBanks
            macroTileHeight = 8 * numPipes

            if expTileMode in [4, 12]:
                if (widtha < widthAlignFactor * macroTileWidth) or heighta < macroTileHeight:
                    expTileMode = 2

            elif expTileMode == 5:
                macroTileWidth >>= 1
                macroTileHeight *= 2

                if (widtha < widthAlignFactor * macroTileWidth) or heighta < macroTileHeight:
                    expTileMode = 2

            elif expTileMode == 6:
                macroTileWidth >>= 2
                macroTileHeight *= 4

                if (widtha < widthAlignFactor * macroTileWidth) or heighta < macroTileHeight:
                    expTileMode = 2

            if expTileMode in [7, 13]:
                if (widtha < widthAlignFactor * macroTileWidth) or heighta < macroTileHeight:
                    expTileMode = 3

            v11 = expTileMode
            if expTileMode == 3:
                if numSlicesa < 4:
                    expTileMode = 2

            elif v11 == 7:
                if numSlicesa < 4:
                    expTileMode = 4

            elif v11 == 13 and numSlicesa < 4:
                expTileMode = 12

            result = computeSurfaceMipLevelTileMode(
                expTileMode,
                bpp,
                level,
                widtha,
                heighta,
                numSlicesa,
                numSamples,
                isDepth,
                1)

        else:
            result = expTileMode

    return result


def isDualPitchAlignNeeded(tileMode, isDepth, mipLevel):
    if isDepth or mipLevel or m_chipFamily != 1:
        needed = 0

    elif tileMode in [0, 1, 2, 3, 7, 11, 13, 15]:
        needed = 0

    else:
        needed = 1

    return needed


def isPow2(dim):
    if dim & (dim - 1) == 0:
        return 1

    else:
        return 0


def padDimensions(tileMode, padDims, isCube, cubeAsArray, pitchAlign, heightAlign, sliceAlign):
    global expPitch
    global expHeight
    global expNumSlices

    thickness = computeSurfaceThickness(tileMode)
    if not padDims:
        padDims = 3

    if isPow2(pitchAlign):
        expPitch = powTwoAlign(expPitch, pitchAlign)

    else:
        expPitch = pitchAlign + expPitch - 1
        expPitch //= pitchAlign
        expPitch *= pitchAlign

    if padDims > 1:
        expHeight = powTwoAlign(expHeight, heightAlign)

    if padDims > 2 or thickness > 1:
        if isCube and ((not ((m_configFlags >> 3) & 1)) or cubeAsArray):
            expNumSlices = nextPow2(expNumSlices)

        if thickness > 1:
            expNumSlices = powTwoAlign(expNumSlices, sliceAlign)

    return expPitch, expHeight, expNumSlices


def adjustPitchAlignment(flags, pitchAlign):
    if (flags.value >> 13) & 1:
        pitchAlign = powTwoAlign(pitchAlign, 0x20)

    return pitchAlign


def computeSurfaceAlignmentsLinear(tileMode, bpp, flags):
    if tileMode:
        if tileMode == 1:
            pixelsPerPipeInterleave = 8 * m_pipeInterleaveBytes // bpp
            baseAlign = m_pipeInterleaveBytes
            pitchAlign = max(0x40, pixelsPerPipeInterleave)
            heightAlign = 1

        else:
            baseAlign = 1
            pitchAlign = 1
            heightAlign = 1

    else:
        baseAlign = 1
        pitchAlign = (1 if bpp != 1 else 8)
        heightAlign = 1

    pitchAlign = adjustPitchAlignment(flags, pitchAlign)

    return baseAlign, pitchAlign, heightAlign


def computeSurfaceInfoLinear(tileMode, bpp, numSamples, pitch, height, numSlices, mipLevel, padDims, flags):
    global expPitch
    global expHeight
    global expNumSlices

    expPitch = pitch
    expHeight = height
    expNumSlices = numSlices

    valid = 1
    microTileThickness = computeSurfaceThickness(tileMode)

    baseAlign, pitchAlign, heightAlign = computeSurfaceAlignmentsLinear(tileMode, bpp, flags)

    if ((flags.value >> 9) & 1) and not mipLevel:
        expPitch //= 3
        expPitch = nextPow2(expPitch)

    if mipLevel:
        expPitch = nextPow2(expPitch)
        expHeight = nextPow2(expHeight)

        if (flags.value >> 4) & 1:
            expNumSlices = numSlices

            if numSlices <= 1:
                padDims = 2

            else:
                padDims = 0

        else:
            expNumSlices = nextPow2(numSlices)

    expPitch, expHeight, expNumSlices = padDimensions(
        tileMode,
        padDims,
        (flags.value >> 4) & 1,
        (flags.value >> 7) & 1,
        pitchAlign,
        heightAlign,
        microTileThickness)

    if ((flags.value >> 9) & 1) and not mipLevel:
        expPitch *= 3

    slices = expNumSlices * numSamples // microTileThickness
    pPitchOut = expPitch
    pHeightOut = expHeight
    pNumSlicesOut = expNumSlices
    pSurfSize = (expHeight * expPitch * slices * bpp * numSamples + 7) // 8
    pBaseAlign = baseAlign
    pPitchAlign = pitchAlign
    pHeightAlign = heightAlign
    pDepthAlign = microTileThickness

    return valid, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign


def computeSurfaceAlignmentsMicroTiled(tileMode, bpp, flags, numSamples):
    if bpp in [24, 48, 96]:
        bpp //= 3

    v8 = computeSurfaceThickness(tileMode)
    baseAlign = m_pipeInterleaveBytes
    pitchAlign = max(8, m_pipeInterleaveBytes // bpp // numSamples // v8)
    heightAlign = 8

    pitchAlign = adjustPitchAlignment(flags, pitchAlign)

    return baseAlign, pitchAlign, heightAlign


def computeSurfaceInfoMicroTiled(tileMode, bpp, numSamples, pitch, height, numSlices, mipLevel, padDims, flags):
    global expPitch
    global expHeight
    global expNumSlices

    expTileMode = tileMode
    expPitch = pitch
    expHeight = height
    expNumSlices = numSlices

    valid = 1
    microTileThickness = computeSurfaceThickness(tileMode)

    if mipLevel:
        expPitch = nextPow2(pitch)
        expHeight = nextPow2(height)
        if (flags.value >> 4) & 1:
            expNumSlices = numSlices

            if numSlices <= 1:
                padDims = 2

            else:
                padDims = 0

        else:
            expNumSlices = nextPow2(numSlices)

        if expTileMode == 3 and expNumSlices < 4:
            expTileMode = 2
            microTileThickness = 1

    baseAlign, pitchAlign, heightAlign = computeSurfaceAlignmentsMicroTiled(
        expTileMode,
        bpp,
        flags,
        numSamples)

    expPitch, expHeight, expNumSlices = padDimensions(
        expTileMode,
        padDims,
        (flags.value >> 4) & 1,
        (flags.value >> 7) & 1,
        pitchAlign,
        heightAlign,
        microTileThickness)

    pPitchOut = expPitch
    pHeightOut = expHeight
    pNumSlicesOut = expNumSlices
    pSurfSize = (expHeight * expPitch * expNumSlices * bpp * numSamples + 7) // 8
    pTileModeOut = expTileMode
    pBaseAlign = baseAlign
    pPitchAlign = pitchAlign
    pHeightAlign = heightAlign
    pDepthAlign = microTileThickness

    return valid, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pTileModeOut, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign


def isDualBaseAlignNeeded(tileMode):
    needed = 1

    if m_chipFamily == 1:
        if 0 <= tileMode <= 3:
            needed = 0

    else:
        needed = 0

    return needed


def computeSurfaceAlignmentsMacroTiled(tileMode, bpp, flags, numSamples):
    groupBytes = m_pipeInterleaveBytes
    numBanks = m_banks
    numPipes = m_pipes
    splitBytes = m_splitSize
    aspectRatio = computeMacroTileAspectRatio(tileMode)
    thickness = computeSurfaceThickness(tileMode)

    if bpp in [24, 48, 96]:
        bpp //= 3

    if bpp == 3:
        bpp = 1

    macroTileWidth = 8 * numBanks // aspectRatio
    macroTileHeight = aspectRatio * 8 * numPipes

    pitchAlign = max(macroTileWidth, macroTileWidth * (groupBytes // bpp // (8 * thickness) // numSamples))
    pitchAlign = adjustPitchAlignment(flags, pitchAlign)

    heightAlign = macroTileHeight
    macroTileBytes = numSamples * ((bpp * macroTileHeight * macroTileWidth + 7) >> 3)

    if m_chipFamily == 1 and numSamples == 1:
        macroTileBytes *= 2

    if thickness == 1:
        baseAlign = max(macroTileBytes, (numSamples * heightAlign * bpp * pitchAlign + 7) >> 3)

    else:
        baseAlign = max(groupBytes, (4 * heightAlign * bpp * pitchAlign + 7) >> 3)

    microTileBytes = (thickness * numSamples * (bpp << 6) + 7) >> 3
    numSlicesPerMicroTile = 1 if microTileBytes < splitBytes else microTileBytes // splitBytes
    baseAlign //= numSlicesPerMicroTile

    if isDualBaseAlignNeeded(tileMode):
        macroBytes = (bpp * macroTileHeight * macroTileWidth + 7) >> 3

        if baseAlign // macroBytes % 2:
            baseAlign += macroBytes

    return baseAlign, pitchAlign, heightAlign, macroTileWidth, macroTileHeight


def computeSurfaceInfoMacroTiled(tileMode, baseTileMode, bpp, numSamples, pitch, height, numSlices, mipLevel, padDims, flags):
    global expPitch
    global expHeight
    global expNumSlices

    expPitch = pitch
    expHeight = height
    expNumSlices = numSlices

    valid = 1
    expTileMode = tileMode
    microTileThickness = computeSurfaceThickness(tileMode)

    if mipLevel:
        expPitch = nextPow2(pitch)
        expHeight = nextPow2(height)

        if (flags.value >> 4) & 1:
            expNumSlices = numSlices
            padDims = 2 if numSlices <= 1 else 0

        else:
            expNumSlices = nextPow2(numSlices)

        if expTileMode == 7 and expNumSlices < 4:
            expTileMode = 4
            microTileThickness = 1

    if (tileMode == baseTileMode
        or not mipLevel
        or not isThickMacroTiled(baseTileMode)
        or isThickMacroTiled(tileMode)):
        baseAlign, pitchAlign, heightAlign, macroWidth, macroHeight = computeSurfaceAlignmentsMacroTiled(
            tileMode,
            bpp,
            flags,
            numSamples)

        bankSwappedWidth = computeSurfaceBankSwappedWidth(tileMode, bpp, pitch, numSamples)

        if bankSwappedWidth > pitchAlign:
            pitchAlign = bankSwappedWidth

        if isDualPitchAlignNeeded(tileMode, (flags.value >> 1) & 1, mipLevel):
            v21 = (m_pipeInterleaveBytes >> 3) // bpp // numSamples
            tilePerGroup = v21 // computeSurfaceThickness(tileMode)

            if not tilePerGroup:
                tilePerGroup = 1

            evenHeight = (expHeight - 1) // macroHeight & 1
            evenWidth = (expPitch - 1) // macroWidth & 1

            if (numSamples == 1
                and tilePerGroup == 1
                and not evenWidth
                and (expPitch > macroWidth or not evenHeight and expHeight > macroHeight)):
                expPitch += macroWidth

        expPitch, expHeight, expNumSlices = padDimensions(
            tileMode,
            padDims,
            (flags.value >> 4) & 1,
            (flags.value >> 7) & 1,
            pitchAlign,
            heightAlign,
            microTileThickness)

        pPitchOut = expPitch
        pHeightOut = expHeight
        pNumSlicesOut = expNumSlices
        pSurfSize = (expHeight * expPitch * expNumSlices * bpp * numSamples + 7) // 8
        pTileModeOut = expTileMode
        pBaseAlign = baseAlign
        pPitchAlign = pitchAlign
        pHeightAlign = heightAlign
        pDepthAlign = microTileThickness
        result = valid

    else:
        baseAlign, pitchAlign, heightAlign, macroWidth, macroHeight = computeSurfaceAlignmentsMacroTiled(
            baseTileMode,
            bpp,
            flags,
            numSamples)

        pitchAlignFactor = (m_pipeInterleaveBytes >> 3) // bpp
        if not pitchAlignFactor:
            pitchAlignFactor = 1

        if expPitch < pitchAlign * pitchAlignFactor or expHeight < heightAlign:
            expTileMode = 2

            result, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pTileModeOut, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign = computeSurfaceInfoMicroTiled(
                2,
                bpp,
                numSamples,
                pitch,
                height,
                numSlices,
                mipLevel,
                padDims,
                flags)

        else:
            baseAlign, pitchAlign, heightAlign, macroWidth, macroHeight = computeSurfaceAlignmentsMacroTiled(
                tileMode,
                bpp,
                flags,
                numSamples)

            bankSwappedWidth = computeSurfaceBankSwappedWidth(tileMode, bpp, pitch, numSamples)
            if bankSwappedWidth > pitchAlign:
                pitchAlign = bankSwappedWidth

            if isDualPitchAlignNeeded(tileMode, (flags.value >> 1) & 1, mipLevel):
                v21 = (m_pipeInterleaveBytes >> 3) // bpp // numSamples
                tilePerGroup = v21 // computeSurfaceThickness(tileMode)

                if not tilePerGroup:
                    tilePerGroup = 1

                evenHeight = (expHeight - 1) // macroHeight & 1
                evenWidth = (expPitch - 1) // macroWidth & 1

                if numSamples == 1 and tilePerGroup == 1 and not evenWidth and (expPitch > macroWidth or not evenHeight and expHeight > macroHeight):
                    expPitch += macroWidth

            expPitch, expHeight, expNumSlices = padDimensions(
                tileMode,
                padDims,
                (flags.value >> 4) & 1,
                (flags.value >> 7) & 1,
                pitchAlign,
                heightAlign,
                microTileThickness)

            pPitchOut = expPitch
            pHeightOut = expHeight
            pNumSlicesOut = expNumSlices
            pSurfSize = (expHeight * expPitch * expNumSlices * bpp * numSamples + 7) // 8
            pTileModeOut = expTileMode
            pBaseAlign = baseAlign
            pPitchAlign = pitchAlign
            pHeightAlign = heightAlign
            pDepthAlign = microTileThickness
            result = valid

    return result, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pTileModeOut, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign


def ComputeSurfaceInfoEx():
    tileMode = pIn.tileMode
    bpp = pIn.bpp
    numSamples = max(1, pIn.numSamples)
    pitch = pIn.width
    height = pIn.height
    numSlices = pIn.numSlices
    mipLevel = pIn.mipLevel
    flags = Flags()
    flags.value = pIn.flags.value
    pPitchOut = pOut.pitch
    pHeightOut = pOut.height
    pNumSlicesOut = pOut.depth
    pTileModeOut = pOut.tileMode
    pSurfSize = pOut.surfSize
    pBaseAlign = pOut.baseAlign
    pPitchAlign = pOut.pitchAlign
    pHeightAlign = pOut.heightAlign
    pDepthAlign = pOut.depthAlign
    padDims = 0
    valid = 0
    baseTileMode = tileMode

    if ((flags.value >> 4) & 1) and not mipLevel:
        padDims = 2

    if ((flags.value >> 6) & 1):
        tileMode = convertToNonBankSwappedMode(tileMode)

    else:
        tileMode = computeSurfaceMipLevelTileMode(
            tileMode,
            bpp,
            mipLevel,
            pitch,
            height,
            numSlices,
            numSamples,
            (flags.value >> 1) & 1,
            0)

    if tileMode in [0, 1]:
        valid, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign = computeSurfaceInfoLinear(
            tileMode,
            bpp,
            numSamples,
            pitch,
            height,
            numSlices,
            mipLevel,
            padDims,
            flags)

        pTileModeOut = tileMode

    elif tileMode in [2, 3]:
        valid, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pTileModeOut, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign = computeSurfaceInfoMicroTiled(
            tileMode,
            bpp,
            numSamples,
            pitch,
            height,
            numSlices,
            mipLevel,
            padDims,
            flags)

    elif tileMode in [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]:
        valid, pPitchOut, pHeightOut, pNumSlicesOut, pSurfSize, pTileModeOut, pBaseAlign, pPitchAlign, pHeightAlign, pDepthAlign = computeSurfaceInfoMacroTiled(
            tileMode,
            baseTileMode,
            bpp,
            numSamples,
            pitch,
            height,
            numSlices,
            mipLevel,
            padDims,
            flags)

    result = 0
    if valid == 0:
        result = 3

    pOut.pitch = pPitchOut
    pOut.height = pHeightOut
    pOut.depth = pNumSlicesOut
    pOut.tileMode = pTileModeOut
    pOut.surfSize = pSurfSize
    pOut.baseAlign = pBaseAlign
    pOut.pitchAlign = pPitchAlign
    pOut.heightAlign = pHeightAlign
    pOut.depthAlign = pDepthAlign

    return result


def restoreSurfaceInfo(elemMode, expandX, expandY, bpp):
    if bpp:
        if elemMode == 4:
            originalBits = expandY * expandX * bpp

        elif elemMode in [5, 6]:
            originalBits = bpp // expandX // expandY

        elif elemMode in [7, 8]:
            originalBits = bpp

        elif elemMode in [9, 12]:
            originalBits = 64

        elif elemMode in [10, 11, 13]:
            originalBits = 128

        elif elemMode in [0, 1, 2, 3]:
            originalBits = bpp

        else:
            originalBits = bpp

        bpp = originalBits

    if pOut.pixelPitch and pOut.pixelHeight:
        width = pOut.pixelPitch
        height = pOut.pixelHeight

        if expandX > 1 or expandY > 1:
            if elemMode == 4:
                width //= expandX
                height //= expandY

            else:
                width *= expandX
                height *= expandY

        pOut.pixelPitch = max(1, width)
        pOut.pixelHeight = max(1, height)

    return bpp


def computeSurfaceInfo(aSurfIn, pSurfOut):
    global pIn
    global pOut
    global ADDR_OK

    pIn = aSurfIn
    pOut = pSurfOut

    v4 = 0
    v6 = 0
    v7 = 0
    v8 = 0
    v10 = 0
    v11 = 0
    v12 = 0
    v18 = 0
    tileInfoNull = tileInfo()
    sliceFlags = 0

    returnCode = 0
    if getFillSizeFieldsFlags() == 1 and (pIn.size != 60 or pOut.size != 96):  # --> m_configFlags.value = 4
        returnCode = 6

    # v3 = pIn

    if pIn.bpp > 0x80:
        returnCode = 3

    if returnCode == ADDR_OK:
        v18 = 0

        computeMipLevel()

        width = pIn.width
        height = pIn.height
        bpp = pIn.bpp
        expandX = 1
        expandY = 1

        sliceFlags = getSliceComputingFlags()

        if useTileIndex(pIn.tileIndex) and pIn.pTileInfo is None:
            if pOut.pTileInfo is not None:
                pIn.pTileInfo = pOut.pTileInfo

            else:
                pOut.pTileInfo = tileInfoNull
                pIn.pTileInfo = tileInfoNull

        returnCode = 0  # does nothing
        if returnCode == ADDR_OK:
            pOut.pixelBits = pIn.bpp

            # v3 = pIn

            if pIn.format:
                v18 = 1
                v4 = pIn.format
                bpp, expandX, expandY, elemMode = getBitsPerPixel(v4)

                if elemMode == 4 and expandX == 3 and pIn.tileMode == 1:
                    pIn.flags.value |= 0x200

                v6 = expandY
                v7 = expandX
                v8 = elemMode
                bpp = adjustSurfaceInfo(v8, v7, v6, bpp, width, height)

            elif pIn.bpp:
                pIn.width = max(1, pIn.width)
                pIn.height = max(1, pIn.height)

            else:
                returnCode = 3

        if returnCode == ADDR_OK:
            returnCode = ComputeSurfaceInfoEx()

        if returnCode == ADDR_OK:
            pOut.bpp = pIn.bpp
            pOut.pixelPitch = pOut.pitch
            pOut.pixelHeight = pOut.height

            if pIn.format and (not ((pIn.flags.value >> 9) & 1) or not pIn.mipLevel):
                if not v18:
                    return

                v10 = expandY
                v11 = expandX
                v12 = elemMode
                bpp = restoreSurfaceInfo(v12, v11, v10, bpp)

            if sliceFlags:
                if sliceFlags == 1:
                    pOut.sliceSize = (pOut.height * pOut.pitch * pOut.bpp * pIn.numSamples + 7) // 8

            elif (pIn.flags.value >> 5) & 1:
                pOut.sliceSize = pOut.surfSize

            else:
                pOut.sliceSize = pOut.surfSize // pOut.depth

                if pIn.slice == (pIn.numSlices - 1) and pIn.numSlices > 1:
                    pOut.sliceSize += pOut.sliceSize * (pOut.depth - pIn.numSlices)

            pOut.pitchTileMax = (pOut.pitch >> 3) - 1
            pOut.heightTileMax = (pOut.height >> 3) - 1
            sliceTileMax = (pOut.height * pOut.pitch >> 6) - 1
            pOut.sliceTileMax = sliceTileMax


def getSurfaceInfo(surfaceFormat, surfaceWidth, surfaceHeight, surfaceDepth, surfaceDim, surfaceTileMode, surfaceAA, level):
    dim = 0
    width = 0
    blockSize = 0
    numSamples = 0
    hwFormat = 0

    aSurfIn = surfaceIn()
    pSurfOut = surfaceOut()

    hwFormat = surfaceFormat & 0x3F
    if surfaceTileMode == 16:
        numSamples = 1 << surfaceAA

        if hwFormat < 0x31 or hwFormat > 0x35:
            blockSize = 1

        else:
            blockSize = 4

        width = ~(blockSize - 1) & ((surfaceWidth >> level) + blockSize - 1)

        if hwFormat == 0x35:
            return pSurfOut

        pSurfOut.bpp = formatHwInfo[hwFormat * 4]
        pSurfOut.size = 96
        pSurfOut.pitch = width // blockSize
        pSurfOut.pixelBits = formatHwInfo[hwFormat * 4]
        pSurfOut.baseAlign = 1
        pSurfOut.pitchAlign = 1
        pSurfOut.heightAlign = 1
        pSurfOut.depthAlign = 1
        dim = surfaceDim

        if dim == 0:
            pSurfOut.height = 1
            pSurfOut.depth = 1

        elif dim == 1:
            pSurfOut.height = max(1, surfaceHeight >> level)
            pSurfOut.depth = 1

        elif dim == 2:
            pSurfOut.height = max(1, surfaceHeight >> level)
            pSurfOut.depth = max(1, surfaceDepth >> level)

        elif dim == 3:
            pSurfOut.height = max(1, surfaceHeight >> level)
            pSurfOut.depth = max(6, surfaceDepth)

        elif dim == 4:
            pSurfOut.height = 1
            pSurfOut.depth = surfaceDepth

        elif dim == 5:
            pSurfOut.height = max(1, surfaceHeight >> level)
            pSurfOut.depth = surfaceDepth

        pSurfOut.height = (~(blockSize - 1) & (pSurfOut.height + blockSize - 1)) // blockSize
        pSurfOut.pixelPitch = ~(blockSize - 1) & ((surfaceWidth >> level) + blockSize - 1)
        pSurfOut.pixelPitch = max(blockSize, pSurfOut.pixelPitch)
        pSurfOut.pixelHeight = ~(blockSize - 1) & ((surfaceHeight >> level) + blockSize - 1)
        pSurfOut.pixelHeight = max(blockSize, pSurfOut.pixelHeight)
        pSurfOut.pitch = max(1, pSurfOut.pitch)
        pSurfOut.height = max(1, pSurfOut.height)
        pSurfOut.surfSize = pSurfOut.bpp * numSamples * pSurfOut.depth * pSurfOut.height * pSurfOut.pitch >> 3

        if surfaceDim == 2:
            pSurfOut.sliceSize = pSurfOut.surfSize

        else:
            pSurfOut.sliceSize = pSurfOut.surfSize // pSurfOut.depth

        pSurfOut.pitchTileMax = (pSurfOut.pitch >> 3) - 1
        pSurfOut.heightTileMax = (pSurfOut.height >> 3) - 1
        pSurfOut.sliceTileMax = (pSurfOut.height * pSurfOut.pitch >> 6) - 1

    else:
        aSurfIn.size = 60
        aSurfIn.tileMode = surfaceTileMode & 0xF
        aSurfIn.format = hwFormat
        aSurfIn.bpp = formatHwInfo[hwFormat * 4]
        aSurfIn.numSamples = 1 << surfaceAA
        aSurfIn.numFrags = aSurfIn.numSamples
        aSurfIn.width = max(1, surfaceWidth >> level)
        dim = surfaceDim

        if dim == 0:
            aSurfIn.height = 1
            aSurfIn.numSlices = 1

        elif dim == 1:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = 1

        elif dim == 2:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = max(1, surfaceDepth >> level)

        elif dim == 3:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = max(6, surfaceDepth)
            aSurfIn.flags.value |= 0x10

        elif dim == 4:
            aSurfIn.height = 1
            aSurfIn.numSlices = surfaceDepth

        elif dim == 5:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = surfaceDepth

        elif dim == 6:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = 1

        elif dim == 7:
            aSurfIn.height = max(1, surfaceHeight >> level)
            aSurfIn.numSlices = surfaceDepth

        aSurfIn.slice = 0
        aSurfIn.mipLevel = level

        if surfaceDim == 2:
            aSurfIn.flags.value |= 0x20

        if level == 0:
            aSurfIn.flags.value = (1 << 12) | aSurfIn.flags.value & 0xFFFFEFFF

        else:
            aSurfIn.flags.value = aSurfIn.flags.value & 0xFFFFEFFF

        pSurfOut.size = 96
        computeSurfaceInfo(aSurfIn, pSurfOut)

        pSurfOut = pOut

    return pSurfOut

BCn_formats = [0x31, 0x431, 0x32, 0x432, 0x33, 0x433, 0x34, 0x234, 0x35, 0x235]
BCn_arg_formats = {0x31: "-bc1", 0x431: "-bc1", 0x32: "-bc2", 0x432: "-bc2", 0x33: "-bc3", 0x433: "-bc3", 0x34: "-bc4", 0x234: "-bc4", 0x35: "-bc5", 0x235: "-bc5"}

########################################################
########################################################
#
#   PyGecko credits:
#
#   Python library: NWPlayer123
#
#   TCPGecko codehandler: Chadderz, Marionumber1
#
########################################################
from binascii import hexlify, unhexlify

def enum(**enums):
    return type('Enum', (), enums)

class TCPGecko:
    def __init__(self, insock):
        self.s = insock
        
        self.data_mem = self.readkern(0xFFEA4E5C)
        self.data_mem_size = self.readkern(0xFFEA4E60)
        
        if not self.validrange(self.data_mem, self.data_mem_size):
            print("Invalid Data Memory Range. Setting to defaults.")
            self.data_mem = 0x10000000
            self.data_mem_size = 0x35000000
        
        print("Sending necessary ASM...")
        self.s.send(tcpGeckoCode)
        print("ASM sent.")

    def readmem(self, address, length, noprint=False): #Number of bytes
        if length == 0: raise BaseException("Reading memory requires a length (# of bytes)")
        if not self.validrange(address, length): raise BaseException("Address range not valid")
        if not self.validaccess(address, length, "read"): raise BaseException("Cannot read from address")
        ret = b""
        if length > 0x400:
            if not noprint: print("Length is greater than 0x400 bytes, need to read in chunks")
            if not noprint: print("Start address:   " + hexstr0(address))
            amount_of_bytes = int(length / 0x400)
            for i in range(amount_of_bytes): #Number of blocks, ignores extra
                self.s.send(b"\x04") #cmd_readmem
                request = struct.pack(">II", address, address + 0x400)
                self.s.send(request)
                status = self.s.recv(1)
                if   status == b"\xbd": ret += self.s.recv(0x400)
                elif status == b"\xb0": ret += b"\x00" * 0x400
                else: raise BaseException("Something went terribly wrong")
                address += 0x400;length -= 0x400
                if not noprint: print("Current address: " + hexstr0(address) + "\t Progress %" + str(round(100.0*i/amount_of_bytes, 2)))
            if length != 0: #Now read the last little bit
                self.s.send(b"\x04")
                request = struct.pack(">II", address, address + length)
                self.s.send(request)
                status = self.s.recv(1)
                if   status == b"\xbd": ret += self.s.recv(length)
                elif status == b"\xb0": ret += b"\x00" * length
                else: raise BaseException("Something went terribly wrong")
            if not noprint: print("Finished!")
        else:
            self.s.send(b"\x04")
            request = struct.pack(">II", address, address + length)
            self.s.send(request)
            status = self.s.recv(1)
            if   status == b"\xbd": ret += self.s.recv(length)
            elif status == b"\xb0": ret += b"\x00" * length
            else: raise BaseException("Something went terribly wrong")
        return ret

    def readkern(self, address): #Only takes 4 bytes, may need to run multiple times
        #if not self.validrange(address, 4): raise BaseException("Address range not valid")
        #if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x0C") #cmd_readkern
        request = struct.pack(">I", int(address))
        self.s.send(request)
        value  = struct.unpack(">I", self.s.recv(4))[0]
        return value

    def writekern(self, address, value): #Only takes 4 bytes, may need to run multiple times
        #if not self.validrange(address, 4): raise BaseException("Address range not valid")
        #if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x0B") #cmd_readkern
        print(value)
        request = struct.pack(">II", int(address), int(value))
        self.s.send(request)
        return

    def pokemem(self, address, value): #Only takes 4 bytes, may need to run multiple times
        if not self.validrange(address, 4): raise BaseException("Address range not valid")
        if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x03") #cmd_pokemem
        request = struct.pack(">II", int(address), int(value))
        self.s.send(request) #Done, move on
        return

    def search32(self, address, value, size):
        self.s.send(b"\x72") #cmd_search32
        request = struct.pack(">III", address, value, size)
        self.s.send(request)
        reply = self.s.recv(4)
        return struct.unpack(">I", reply)[0]

    def getversion(self):
        self.s.send(b"\x9A") #cmd_os_version
        reply = self.s.recv(4)
        return struct.unpack(">I", reply)[0]

    def writestr(self, address, string):
        if not self.validrange(address, len(string)): raise BaseException("Address range not valid")
        if not self.validaccess(address, len(string), "write"): raise BaseException("Cannot write to address")
        if type(string) != bytes: string = bytes(string, "UTF-8") #Sanitize
        if len(string) % 4: string += bytes((4 - (len(string) % 4)) * b"\x00")
        pos = 0
        for x in range(int(len(string) / 4)):
            self.pokemem(address, struct.unpack(">I", string[pos:pos + 4])[0])
            address += 4;pos += 4
        return
        
    def memalign(self, size, align):
        symbol = self.get_symbol("coreinit.rpl", "MEMAllocFromDefaultHeapEx", True, 1)
        symbol = struct.unpack(">I", symbol.address)[0]
        address = self.readmem(symbol, 4)
        #print("memalign address: " + hexstr0(struct.unpack(">I", address)[0]))
        ret = self.call(address, size, align)
        return ret

    def freemem(self, address):
        symbol = self.get_symbol("coreinit.rpl", "MEMFreeToDefaultHeap", True, 1)
        symbol = struct.unpack(">I", symbol.address)[0]
        addr = self.readmem(symbol, 4)
        #print("freemem address: " + hexstr0(struct.unpack(">I", addr)[0]))
        self.call(addr, address) #void, no return

    def memalloc(self, size, align, noprint=False):
        return self.function("coreinit.rpl", "OSAllocFromSystem", noprint, 0, size, align)

    def freealloc(self, address):
        return self.function("coreinit.rpl", "OSFreeToSystem", True, 0, address)

    def createpath(self, path):
        if not hasattr(self, "pPath"): self.pPath = self.memalloc(len(path), 0x20, True) #It'll auto-pad
        size = len(path) + (32 - (len(path) % 32))
        self.function("coreinit.rpl", "memset", True, 0, self.pPath, 0x00, size)
        self.writestr(self.pPath, path)
        #print("pPath address: " + hexstr0(self.pPath))

    def createstr(self, string):
        address = self.memalloc(len(string), 0x20, True) #It'll auto-pad
        size = len(string) + (32 - (len(string) % 32))
        self.function("coreinit.rpl", "memset", True, 0, address, 0x00, size)
        self.writestr(address, string)
        print("String address: " + hexstr0(address))
        return address

    def FSInitClient(self):
        self.pClient = self.memalign(0x1700, 0x20)
        self.function("coreinit.rpl", "FSAddClient", True, 0, self.pClient)
        #print("pClient address: " + hexstr0(self.pClient))

    def FSInitCmdBlock(self):
        self.pCmd = self.memalign(0xA80, 0x20)
        self.function("coreinit.rpl", "FSInitCmdBlock", True, 0, self.pCmd)
        #print("pCmd address:    " + hexstr0(self.pCmd))

    def FSOpenDir(self, path="/"):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True)
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        print("Getting memory ready...")
        self.createpath(path)
        self.pDh   = self.memalloc(4, 4, True)
        #print("pDh address: " + hexstr0(self.pDh))
        print("Calling function...")
        ret = self.function("coreinit.rpl", "FSOpenDir", False, 0, self.pClient, self.pCmd, self.pPath, self.pDh, 0xFFFFFFFF)
        self.pDh = int(hexlify(self.readmem(self.pDh, 4)), 16)
        print("Return value: " + hexstr0(ret))

    def SAVEOpenDir(self, path="/", slot=255):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True, 0)
        self.function("nn_save.rpl", "SAVEInit", True, 0, slot)
        print("Getting memory ready...")
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        self.createpath(path)
        self.pDh   = self.memalloc(4, 4, True)
        #print("pDh address: " + hexstr0(self.pDh))
        print("Calling function...")
        ret = self.function("nn_save.rpl", "SAVEOpenDir", False, 0, self.pClient, self.pCmd, slot, self.pPath, self.pDh, 0xFFFFFFFF)
        self.pDh = int(hexlify(self.readmem(self.pDh, 4)), 16)
        print("Return value: " + hexstr0(ret))

    def FSReadDir(self):
        global printe
        if not hasattr(self, "pBuffer"): self.pBuffer = self.memalign(0x164, 0x20)
        print("pBuffer address: " + hexstr0(self.pBuffer))
        ret = self.function("coreinit.rpl", "FSReadDir", True, 0, self.pClient, self.pCmd, self.pDh, self.pBuffer, 0xFFFFFFFF)
        self.entry = self.readmem(self.pBuffer, 0x164)
        printe = getstr(self.entry, 100) + " "
        self.FileSystem().printflags(uint32(self.entry, 0), self.entry)
        self.FileSystem().printperms(uint32(self.entry, 4))
        print(printe)
        return self.entry, ret

    def SAVEOpenFile(self, path="/", mode="r", slot=255):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True)
        self.function("nn_save.rpl", "SAVEInit", slot, True)
        print("Getting memory ready...")
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        self.createpath(path)
        self.pMode = self.createstr(mode)
        self.pFh   = self.memalign(4, 4)
        #print("pFh address: " + hexstr0(self.pFh))
        print("Calling function...")
        print("This function may have errors")
        #ret = self.function("nn_save.rpl", "SAVEOpenFile", self.pClient, self.pCmd, slot, self.pPath, self.pMode, self.pFh, 0xFFFFFFFF)
        #self.pFh = int(self.readmem(self.pFh, 4).encode("hex"), 16)
        #print(ret)

    def FSReadFile(self):
        if not hasattr(self, "pBuffer"): self.pBuffer = self.memalign(0x200, 0x20)
        print("pBuffer address: " + hexstr0(self.pBuffer))
        ret = self.function("coreinit.rpl", "FSReadFile", False, 0, self.pClient, self.pCmd, self.pBuffer, 1, 0x200, self.pFh, 0, 0xFFFFFFFF)
        print(ret)
        return tcp.readmem(self.pBuffer, 0x200)

    def get_symbol(self, rplname, symname, noprint=False, data=0):
        self.s.send(b"\x71") #cmd_getsymbol
        request = struct.pack(">II", 8, 8 + len(rplname) + 1) #Pointers
        request += rplname.encode("UTF-8") + b"\x00"
        request += symname.encode("UTF-8") + b"\x00"
        size = struct.pack(">B", len(request))
        data = struct.pack(">B", data)
        self.s.send(size) #Read this many bytes
        self.s.send(request) #Get this symbol
        self.s.send(data) #Is it data?
        address = self.s.recv(4)
        return ExportedSymbol(address, self, rplname, symname, noprint)

    def call(self, address, *args):
        arguments = list(args)
        if len(arguments)>8 and len(arguments)<=16: #Use the big call function
            while len(arguments) != 16:
                arguments.append(0)
            self.s.send(b"\x80")
            address = struct.unpack(">I", address)[0]
            request = struct.pack(">I16I", address, *arguments)
            self.s.send(request)
            reply = self.s.recv(8)
            return struct.unpack(">I", reply[:4])[0]
        elif len(arguments) <= 8: #Use the normal one that dNet client uses
            while len(arguments) != 8:
                arguments.append(0)
            self.s.send(b"\x70")
            address = struct.unpack(">I", address)[0]
            request = struct.pack(">I8I", address, *arguments)
            self.s.send(request)
            reply = self.s.recv(8)
            return struct.unpack(">I", reply[:4])[0]
        else: raise BaseException("Too many arguments!")

    #Data last, only a few functions need it, noprint for the big FS/SAVE ones above, acts as gateway for data arg
    def function(self, rplname, symname, noprint=False, data=0, *args):
        symbol = self.get_symbol(rplname, symname, noprint, data)
        ret = self.call(symbol.address, *args)
        return ret

    def validrange(self, address, length):
        if   0x01000000 <= address and address + length <= 0x01800000: return True
        elif 0x0E000000 <= address and address + length <= 0x10000000: return True #Depends on game
        elif 0x10000000 <= address and address + length <= 0x50000000: return True #Doesn't quite go to 5
        elif 0xE0000000 <= address and address + length <= 0xE4000000: return True
        elif 0xE8000000 <= address and address + length <= 0xEA000000: return True
        elif 0xF4000000 <= address and address + length <= 0xF6000000: return True
        elif 0xF6000000 <= address and address + length <= 0xF6800000: return True
        elif 0xF8000000 <= address and address + length <= 0xFB000000: return True
        elif 0xFB000000 <= address and address + length <= 0xFB800000: return True
        elif 0xFFFE0000 <= address and address + length <= 0xFFFFFFFF: return True
        else: return False

    def validaccess(self, address, length, access):
        if   0x01000000 <= address and address + length <= 0x01800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0x0E000000 <= address and address + length <= 0x10000000: #Depends on game, may be EG 0x0E3
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0x10000000 <= address and address + length <= 0x50000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return True
        elif 0xE0000000 <= address and address + length <= 0xE4000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xE8000000 <= address and address + length <= 0xEA000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF4000000 <= address and address + length <= 0xF6000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF6000000 <= address and address + length <= 0xF6800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF8000000 <= address and address + length <= 0xFB000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xFB000000 <= address and address + length <= 0xFB800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xFFFE0000 <= address and address + length <= 0xFFFFFFFF:
            if access.lower() == "read":  return True
            if access.lower() == "write": return True
        else: return False
        
    class FileSystem: #TODO: Try to clean this up ????
        Flags = enum(
            IS_DIRECTORY    = 0x80000000,
            IS_QUOTA        = 0x40000000,
            SPRT_QUOTA_SIZE = 0x20000000, #Supports .quota_size field
            SPRT_ENT_ID     = 0x10000000, #Supports .ent_id field
            SPRT_CTIME      = 0x08000000, #Supports .ctime field
            SPRT_MTIME      = 0x04000000, #Supports .mtime field
            SPRT_ATTRIBUTES = 0x02000000, #Supports .attributes field
            SPRT_ALLOC_SIZE = 0x01000000, #Supports .alloc_size field
            IS_RAW_FILE     = 0x00800000, #Entry isn't encrypted
            SPRT_DIR_SIZE   = 0x00100000, #Supports .size field, doesn't apply to files
            UNSUPPORTED_CHR = 0x00080000) #Entry name has an unsupported character
        
        Permissions = enum( #Pretty self explanitory
            OWNER_READ  = 0x00004000,
            OWNER_WRITE = 0x00002000,
            OTHER_READ  = 0x00000400,
            OTHER_WRITE = 0x00000200)

        def printflags(self, flags, data):
            global printe
            if flags & self.Flags.IS_DIRECTORY:    printe += " Directory"
            if flags & self.Flags.IS_QUOTA:        printe += " Quota"
            if flags & self.Flags.SPRT_QUOTA_SIZE: printe += " .quota_size: " + hexstr0(uint32(data, 24))
            if flags & self.Flags.SPRT_ENT_ID:     printe += " .ent_id: " + hexstr0(uint32(data, 32))
            if flags & self.Flags.SPRT_CTIME:      printe += " .ctime: " + hexstr0(uint32(data, 36))
            if flags & self.Flags.SPRT_MTIME:      printe += " .mtime: " + hexstr0(uint32(data, 44))
            if flags & self.Flags.SPRT_ATTRIBUTES: pass #weh
            if flags & self.Flags.SPRT_ALLOC_SIZE: printe += " .alloc_size: " + hexstr0(uint32(data, 20))
            if flags & self.Flags.IS_RAW_FILE:     printe += " Raw (Unencrypted) file"
            if flags & self.Flags.SPRT_DIR_SIZE:   printe += " .dir_size: " + hexstr0(uint64(data, 24))
            if flags & self.Flags.UNSUPPORTED_CHR: printe += " !! UNSUPPORTED CHARACTER IN NAME"

        def printperms(self, perms):
            global printe
            if perms & self.Permissions.OWNER_READ:  printe += " OWNER_READ"
            if perms & self.Permissions.OWNER_WRITE: printe += " OWNER_WRITE"
            if perms & self.Permissions.OTHER_READ:  printe += " OTHER_READ"
            if perms & self.Permissions.OTHER_WRITE: printe += " OTHER_WRITE"
                
def hexstr0(data): #0xFFFFFFFF, uppercase hex string
    return "0x" + hex(data).lstrip("0x").rstrip("L").zfill(8).upper()

class ExportedSymbol(object):
    def __init__(self, address, rpc=None, rplname=None, symname=None, noprint=False):
        self.address = address
        self.rpc     = rpc
        self.rplname = rplname
        self.symname = symname
        if not noprint: #Make command prompt not explode when using FS or SAVE functions
            print(symname + " address: " + hexstr0(struct.unpack(">I", address)[0]))

    def __call__(self, *args):
        return self.rpc.call(self.address, *args) #Pass in arguments, run address


########################################################
########################################################

def SaveBFTEX(ftex, tname, level, img, operator=None):
            
    if len(img.pixels[:]) == 0:
        if operator is not None:
            operator.report({'ERROR'}, "Failed to get source image data.")
        print("Failed to get source image data.")
        return
      ### FTEX ENCODER BASED HEAVILY FROM BFRES-TOOL BY ABOODXD ###
    format_ = ftex.format()
    if ftex.num_bitmaps() > 14:
        if operator is not None: operator.report({'WARNING'}, "Number of mipmaps (%s) exceeded maximum (13) in model %s" % (str(ftex.num_bitmaps()-1), bpy.context.scene.bfres.data.get_model_name(i)))
        print("\tError: Number of mipmaps (%s) exceeded maximum (13) in model %s" % (str(ftex.num_bitmaps()-1), bpy.context.scene.bfres.data.get_model_name(i)))
        return

    mipOffsets = []
    for i in range(13):
        mipOffsets.append(ftex.get_relative_mipmap_offset(i))

    compSelBytes = ftex.get_component_selector()
    compSel = []
    for i in range(4):
        comp = compSelBytes[i]
        if comp == 4: # Sorry, but this is unsupported.
            comp = i
        compSel.append(comp)

    dataSize = ftex.data_length()
    data_pos = ftex.data_offset()
    mip_pos = ftex.mipmap_offset()
    base_data_size = mip_pos
    numMips = ftex.num_bitmaps()
    width = ftex.width()
    height = ftex.height()
    depth = ftex.depth()
    dim = ftex.surface_dimension()
    aa = ftex.aa()
    tileMode = ftex.tile_mode()
    swizzle_ = ftex.swizzle_value()
    bpp = surfaceGetBitsPerPixel(format_) >> 3

    total_original_size = ftex.data_length() + ftex.mipmap_data_length()
    surfOut = getSurfaceInfo(format_, width, height, depth, dim, tileMode, aa, 0)
    datasize = surfOut.surfSize

    if aa:
        if operator is not None: operator.report({'ERROR'}, "Unsupported texture AA mode detected: %s in model %s" % (str(aa), bpy.context.scene.bfres.data.get_model_name(i)))
        print("\tError: Unsupported texture AA mode detected: %s in model %s" % (str(aa), bpy.context.scene.bfres.data.get_model_name(i)))
        return

    if surfOut.depth != 1:
        if operator is not None: operator.report({'ERROR'}, "Unsupported texture depth detected: %s in model %s" % (str(surfOut.depth), bpy.context.scene.bfres.data.get_model_name(i)))
        print("\tError: Unsupported texture depth detected: %s in model %s" % (str(surfOut.depth), bpy.context.scene.bfres.data.get_model_name(i)))
        return
    resize = False
    if level == -1:
        levels = range(numMips)
        ftex.num_bitmaps_again(numMips)
        width = ftex.width(img.size[0])
        height = ftex.height(img.size[1])
        surfOut = getSurfaceInfo(format_, width, height, depth, dim, tileMode, aa, 0)
        datasize = surfOut.surfSize
        resize = True
    else: levels = [level]
    out_data = b''
    for level in levels:
        print("Encoding Texture Mipmap %i." % level)
        data_offset = data_pos
        if level != 0:
            if level == 1:
                mipOffset = mipOffsets[level - 1] - surfOut.surfSize
            else:
                mipOffset = mipOffsets[level - 1]
            data_offset = mip_pos + mipOffset
            surfOut = getSurfaceInfo(format_, width, height, depth, dim, tileMode, aa, level)

            datasize = surfOut.surfSize
            
        mipwidth, mipheight = max(1, width >> level), max(1, height >> level)
        if format_ in BCn_formats:
            size = ((max(1, width >> level) + 3) >> 2) * ((max(1, height >> level) + 3) >> 2) * bpp
        else:
            size = max(1, width >> level) * max(1, height >> level) * bpp
        data = b''

        pixels = img.pixels[:]


        if format_ in BCn_formats:
            tga_file = open(bpy.context.user_preferences.filepaths.temporary_directory+"process_img.tga", "wb")
            tga_file.write(b'\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00' + struct.pack("2H", mipwidth, mipheight) + b'\x20\x08')
            cmd = BCn_arg_formats[format_]
            for y in range(mipheight):
                print("Encoding progress: \t%s\t\t\t" % (str(y*100/mipheight)+"%"), end="\r")
                for x in range(mipwidth):
                    rely = int(round(((y/mipheight)*img.size[1]), 2))
                    relx = int(round(((x/mipwidth)*img.size[0]), 2))
                    if rely < 0: rely = 0
                    if rely >= img.size[1]: rely = img.size[1]-1
                    if relx < 0: relx = 0
                    if relx >= img.size[0]: relx = img.size[0]-1
                    r = pixels[(rely*img.size[0]+relx)*4+0]
                    g = pixels[(rely*img.size[0]+relx)*4+1]
                    b = pixels[(rely*img.size[0]+relx)*4+2]
                    a = pixels[(rely*img.size[0]+relx)*4+3]
                    if cmd == "-bc4":
                        a = 0.21*r+0.72*g+0.07*b

                    tga_file.write(struct.pack("BBBB", int(round(b*255)), int(round(g*255)), int(round(r*255)), int(round(a*255))))
            print("")
            tga_file.close()
            if platform == "win32":
                subprocess.call([bpy.context.user_preferences.filepaths.temporary_directory+"nvcompress.exe", cmd, bpy.context.user_preferences.filepaths.temporary_directory+"process_img.tga", bpy.context.user_preferences.filepaths.temporary_directory+"process_img.dds"])
                f = open(bpy.context.user_preferences.filepaths.temporary_directory+"process_img.dds", "rb")
                f.seek(0x80)
                data = f.read()
                f.close()
            else:
                # On Ubuntu, you can install nvcompress with "sudo apt install libnvtt{,-dev,-bin}".
                subprocess.call(["nvcompress", cmd, bpy.context.user_preferences.filepaths.temporary_directory+"process_img.tga", bpy.context.user_preferences.filepaths.temporary_directory+"process_img.dds"])
                f = open(bpy.context.user_preferences.filepaths.temporary_directory+"process_img.dds", "rb")
                f.seek(0x80)
                data = f.read()
                f.close()
            if cmd == "-bc2":
                fixData = b''
                while len(fixData) < len(data):
                    s = len(fixData)
                    alpha = data[s:s+8]
                    fixAlpha = b''
                    for i in range(8):
                        fixAlpha+=struct.pack("B", ((alpha[i]&0xF)<<4)|(alpha[i]>>4))
                    rgb = data[s+8:s+16]
                    
                    fixData += fixAlpha + rgb
                data = fixData
            elif (cmd == "-bc4") or (cmd == "-bc5") and (format_&0x200):
                fixData = b''
                while len(fixData) < len(data):
                    s = len(fixData)
                    v1 = data[s]
                    v2 = data[s+1]
                    tweens = data[s+2:s+8]
                    
                    v1-=0x80
                    v2-=0x80
                    
                    if v1 < 0: v1+=0x100
                    if v2 < 0: v2+=0x100
                    
                    fixData += struct.pack("BB", v1, v2) + tweens
                data = fixData
                
            data += b'\0'*max(0,datasize-len(data))
        else:
            i = 0
            while len(data) < datasize:
                x = i%mipwidth
                y = i//mipwidth
                rely = int(round(((y/mipheight)*img.size[1]), 2))
                relx = int(round(((x/mipwidth)*img.size[0]), 2))
                if rely < 0: rely = 0
                if rely >= img.size[1]: rely = img.size[1]-1
                if relx < 0: relx = 0
                if relx >= img.size[0]: relx = img.size[0]-1
                r = pixels[(rely*img.size[0]+relx)*4+0]
                g = pixels[(rely*img.size[0]+relx)*4+1]
                b = pixels[(rely*img.size[0]+relx)*4+2]
                a = pixels[(rely*img.size[0]+relx)*4+3]
                if format_&0x1a == 0x1a: data += struct.pack("BBBB", int(round(r*255)), int(round(g*255)), int(round(b*255)), int(round(a*255)))
                elif format_&0x19 == 0x19:
                    data += struct.pack("I", (int(round(r*1023))&0x3FF)|((int(round(g*1023))&0x3FF) << 10)|((int(round(b*1023))&0x3FF) << 20)|((int(round(a*3))&0x3) << 30))
                elif format_ == 0xa:
                    data += struct.pack("H", (int(round(a))&0x1)|((int(round(b*31))&0x1F)<<1)|((int(round(g*31))&0x1F)<<6)|((int(round(r*31))&0x1F)<<11))
                elif format_ == 0xb:
                    data += struct.pack("H", (int(round(r*15))&0xF)|((int(round(g*15))&0xF) << 4)|((int(round(b*15))&0xF) << 8)|((int(round(a*15))&0xF) << 12))
                elif format_ == 0x8:
                    data += struct.pack("H", encode_rgb565(r,g,b))
                elif format_ == 0x107 or format_ == 0x7:
                    data += struct.pack("BB", int(round((0.21*r+0.72*g+0.07*b)*255)), int(round(a*255)))
                elif format_ == 0x1 or format_ == 0x101:
                    data += struct.pack("B", int(round((0.21*r+0.72*g+0.07*b)*255)))
                else:
                    if operator is not None: operator.report({'ERROR'}, "Unrecognized texture format detected: %s" % (ftex.format_string()))
                    print("\tError: Unrecognized texture format detected: %s" % (ftex.format_string()))
                    return
                i+=1
        pre_out_data_length = len(out_data)
        out_data += swizzle(mipwidth, mipheight, surfOut.height, format_, surfOut.tileMode, swizzle_, surfOut.pitch, surfOut.bpp, data[:datasize])
        if resize:
            if level == 0:
                ftex.mipmap_offset(data_pos + datasize)
                base_data_size = datasize
                dataSize = ftex.data_length(datasize)
            elif level == 1:
                ftex.get_relative_mipmap_offset(level - 1, dataSize)
            else:
                ftex.get_relative_mipmap_offset(level - 1, pre_out_data_length - dataSize)
                
            data_offset = data_pos
            if (mipwidth, mipheight) == (1,1):
                ftex.num_bitmaps_again(level+1)
                break
    if resize:
        removeExtDatItems = []
        for extdatItem in bpy.context.scene.bfres.data.extra_data:
            if extdatItem["id"] == ftex.offset:
                total_original_size = extdatItem["orig_data_size"]
                data_offset = ftex.data_offset(extdatItem["orig_data_offset"])
                ftex.mipmap_offset(data_offset+base_data_size)
                removeExtDatItems.append(extdatItem)
        for extdatItem in removeExtDatItems:
            bpy.context.scene.bfres.data.extra_data.remove(extdatItem)
        ftex.mipmap_data_length(len(out_data) - dataSize)
        if len(out_data) > total_original_size:
            pointers = []
            pointers.append({"pointer_offset": ftex.offset+0xB0, "data_offset": 0})
            pointers.append({"pointer_offset": ftex.offset+0xB4, "data_offset": dataSize})
            bpy.context.scene.bfres.data.extra_data.append({"id": ftex.offset, "data": out_data, "orig_data_size": total_original_size, "orig_data_offset": data_offset, "pointers": pointers})
        else:
            bpy.context.scene.bfres.data.bytes = bpy.context.scene.bfres.data.bytes[:data_offset] + out_data + bpy.context.scene.bfres.data.bytes[data_offset+len(out_data):]
    else:
        inExtra = None
        for itemID in range(len(bpy.context.scene.bfres.data.extra_data)):
            if bpy.context.scene.bfres.data.extra_data[itemID]["id"] == ftex.offset:
                inExtra = (bpy.context.scene.bfres.data.extra_data[itemID].get("data_offset"), itemID)
        if inExtra is None:
            bpy.context.scene.bfres.data.bytes = bpy.context.scene.bfres.data.bytes[:data_offset] + out_data + bpy.context.scene.bfres.data.bytes[data_offset+len(out_data):]
        else:
            if inExtra[0] is not None:
                bpy.context.scene.bfres.data.extra_data[inExtra[1]]["data"] = bpy.context.scene.bfres.data.extra_data[inExtra[1]]["data"][:data_offset-inExtra[0]] + out_data + bpy.context.scene.bfres.data.extra_data[inExtra[1]]["data"][data_offset+len(out_data)-inExtra[0]:]
    bpy.context.scene.bfres.data.apply_extra_data()
    
    
    
def LoadBFTEX(ftex, tname, level, img=None, pack=False, operator=None):
            if pack:
                if tname in bpy.data.images:
                    bpy.data.images.remove(bpy.data.images[tname])
            
      ### FTEX DECODER BASED HEAVILY FROM BFRES-TOOL BY ABOODXD ###
            
            format_ = ftex.format()
            if ftex.num_bitmaps() > 14:
                if operator is not None: operator.report({'WARNING'}, "Number of mipmaps (%s) exceeded maximum (13)" % (str(ftex.num_bitmaps()-1)))
                print("\tError: Number of mipmaps (%s) exceeded maximum (13)" % (str(ftex.num_bitmaps()-1)))
                return

            mipOffsets = []
            for i in range(13):
                mipOffsets.append(ftex.get_relative_mipmap_offset(i))

            compSelBytes = ftex.get_component_selector()
            compSel = []
            for i in range(4):
                comp = compSelBytes[i]
                if comp == 4: # Sorry, but this is unsupported.
                    comp = i
                compSel.append(comp)

            dataSize = ftex.data_length()
            mipSize = ftex.mipmap_data_length()
            data_pos = ftex.data_offset()
            mip_pos = ftex.mipmap_offset()

            data = bpy.context.scene.bfres.data.bytes[data_pos:data_pos+dataSize]

            if not (mip_pos and mipSize):
                mipData = b""
            else:
                mipData = bpy.context.scene.bfres.data.bytes[mip_pos:mip_pos+mipSize]

            numMips = ftex.num_bitmaps()
            width = ftex.width()
            height = ftex.height()
            depth = ftex.depth()
            dim = ftex.surface_dimension()
            aa = ftex.aa()
            tileMode = ftex.tile_mode()
            swizzle_ = ftex.swizzle_value()
            bpp = surfaceGetBitsPerPixel(format_) >> 3

            if format_ in BCn_formats:
                realSize = ((width + 3) >> 2) * ((height + 3) >> 2) * bpp
            else:
                realSize = width * height * bpp

            surfOut = getSurfaceInfo(format_, width, height, depth, dim, tileMode, aa, 0)

            if aa:
                if operator is not None: operator.report({'ERROR'}, "Unsupported texture AA mode detected: %s in model %s" % (str(aa)))
                print("\tError: Unsupported texture AA mode detected: %s in model %s" % (str(aa)))
                return

            if surfOut.depth != 1:
                if operator is not None: operator.report({'ERROR'}, "Unsupported texture depth detected: %s" % (str(surfOut.depth), bpy.context.scene.bfres.data.get_model_name(i)))
                print("\tError: Unsupported texture depth detected: %s" % (str(surfOut.depth), bpy.context.scene.bfres.data.get_model_name(i)))
                return

            if level != 0:
                if level == 1:
                    mipOffset = mipOffsets[level - 1] - surfOut.surfSize
                else:
                    mipOffset = mipOffsets[level - 1]

                surfOut = getSurfaceInfo(format_, width, height, depth, dim, tileMode, aa, level)

                data = mipData[mipOffset:mipOffset + surfOut.surfSize]
            mipwidth, mipheight = max(1, width >> level), max(1, height >> level)
            
            deswizzled = deswizzle(mipwidth, mipheight, surfOut.height, format_, surfOut.tileMode, swizzle_, surfOut.pitch, surfOut.bpp, data)
            
            

            if format_ in BCn_formats:
                size = ((max(1, width >> level) + 3) >> 2) * ((max(1, height >> level) + 3) >> 2) * bpp
            else:
                size = max(1, width >> level) * max(1, height >> level) * bpp
            
            rawdata = deswizzled[:size]
            
            if format_&0x1a == 0x1a: data = [rdb/255 for rdb in rawdata]
            elif format_&0x19 == 0x19:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(0, len(rawdata), 4):
                    rgb10a2 = struct.unpack("I", rawdata[i:i+4])[0]
                    data[pi] = (rgb10a2 & 0x3FF)/1023
                    data[pi+1] = ((rgb10a2 >> 10) & 0x3FF)/1023
                    data[pi+2] = ((rgb10a2 >> 20) & 0x3FF)/1023
                    data[pi+3] = ((rgb10a2 >> 30) & 0x3)/3
                    pi += 4
            elif format_ == 0xa:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(0, len(rawdata), 2):
                    rgb5a1 = struct.unpack("H", rawdata[i:i+2])[0]
                    data[pi] = ((rgb5a1 >> 11) & 0x1F)/31
                    data[pi+1] = ((rgb5a1 >> 6) & 0x1F)/31
                    data[pi+2] = ((rgb5a1 >> 1) & 0x1F)/31
                    data[pi+3] = (rgb5a1 & 0x1)
                    pi += 4
            elif format_ == 0xb:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(0, len(rawdata), 2):
                    rgba4 = struct.unpack("H", rawdata[i:i+2])[0]
                    data[pi] = ((rgba4) & 0xF)/15
                    data[pi+1] = ((rgba4 >> 4) & 0xF)/15
                    data[pi+2] = ((rgba4 >> 8) & 0xF)/15
                    data[pi+3] = ((rgba4 >> 12) & 0xF)/15
                    pi += 4
            elif format_ == 0x8:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(0, len(rawdata), 2):
                    r5g6b5 = struct.unpack("H", rawdata[i:i+2])[0]
                    data[pi] = ((r5g6b5) & 0x1F)/31
                    data[pi+1] = ((r5g6b5 >> 5) & 0x3F)/63
                    data[pi+2] = ((r5g6b5 >> 11) & 0x1F)/31
                    data[pi+3] = 1
                    pi += 4
            elif format_ == 0x107 or format_ == 0x7:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(0, len(rawdata), 2):
                    rg8 = rawdata[i:i+2]
                    data[pi] = rg8[0]/255
                    data[pi+1] = rg8[0]/255
                    data[pi+2] = rg8[0]/255
                    data[pi+3] = rg8[1]/255
                    pi += 4
            elif format_ == 0x1 or format_ == 0x101:
                data = [0 for i in range(mipwidth*mipheight*4)]
                pi = 0
                for i in range(len(rawdata)):
                    data[pi] = rawdata[i]/255
                    data[pi+1] = rawdata[i]/255
                    data[pi+2] = rawdata[i]/255
                    data[pi+3] = 1
                    pi += 4
            elif format_ == 0x31 or format_ == 0x431:
                data = [0 for i in range(mipwidth*mipheight*4)]
                tx = ty = 0
                for i in range(0, len(rawdata), 8):
                    rgbbits = struct.unpack("<2H", rawdata[i:i+4])
                    rgb1 = decode_rgb565(rgbbits[0])
                    rgb2 = decode_rgb565(rgbbits[1])
                    rgb_tween_bits = struct.unpack("<I", rawdata[i+4:i+8])[0]
                    x = y = 0
                    for j in range(16):
                        rgb_val = (rgb_tween_bits>>((j)*2))&0x3
                        a = 1
                        if rgbbits[0] <= rgbbits[1]:
                            if rgb_val == 0:
                                tween = 0
                            elif rgb_val == 1:
                                tween = 1
                            elif rgb_val == 2:
                                tween = 1/2
                            elif rgb_val == 3:
                                tween = 0
                                a = 0
                        else:
                            if rgb_val == 0:
                                tween = 0
                            elif rgb_val == 1:
                                tween = 1
                            elif rgb_val == 2:
                                tween = 1/3
                            elif rgb_val == 3:
                                tween = 2/3
                        rgb = lerp_color(rgb1, rgb2, tween)
                        if (tx+x) < mipwidth and (ty+y) < mipheight:
                            data[(((ty+y)*mipwidth)+(tx+x))*4:(((ty+y)*mipwidth)+(tx+x))*4+4] = [rgb[0], rgb[1], rgb[2], a]
                        
                        x+=1
                        if x >= 4:
                            x = 0
                            y+=1
                    tx+=4
                    if tx >= mipwidth:
                        tx=0
                        ty+=4
            elif format_ == 0x32 or format_ == 0x432:
                data = [0 for i in range(mipwidth*mipheight*4)]
                tx = ty = 0
                for i in range(0, len(rawdata), 16):
                    alphabits = struct.unpack(">Q", rawdata[i:i+8])[0]
                    rgbbits = struct.unpack("<2H", rawdata[i+8:i+12])
                    rgb1 = decode_rgb565(rgbbits[0])
                    rgb2 = decode_rgb565(rgbbits[1])
                    rgb_tween_bits = struct.unpack("<I", rawdata[i+12:i+16])[0]
                    x = y = 0
                    for j in range(16):
                        rgb_val = (rgb_tween_bits>>((j)*2))&0x3
                        a = ((alphabits>>((15-j)*4))&0xF)/15
                        if rgb_val == 0:
                            tween = 0
                        elif rgb_val == 1:
                            tween = 1
                        elif rgb_val == 2:
                            tween = 1/3
                        elif rgb_val == 3:
                            tween = 2/3
                        rgb = lerp_color(rgb1, rgb2, tween)
                        if (tx+x) < mipwidth and (ty+y) < mipheight:
                            data[(((ty+y)*mipwidth)+(tx+x))*4:(((ty+y)*mipwidth)+(tx+x))*4+4] = [rgb[0], rgb[1], rgb[2], a]
                        
                        x+=1
                        if x >= 4:
                            x = 0
                            y+=1
                    tx+=4
                    if tx >= mipwidth:
                        tx=0
                        ty+=4
            elif format_ == 0x33 or format_ == 0x433:
                data = [0 for i in range(mipwidth*mipheight*4)]
                tx = ty = 0
                for i in range(0, len(rawdata), 16):
                    a1 = rawdata[i]/255
                    a2 = rawdata[i+1]/255
                    alpha_tween_bits = struct.unpack("Q", rawdata[i:i+8])[0] >> 16
                    rgbbits = struct.unpack("<2H", rawdata[i+8:i+0xC])
                    rgb1 = decode_rgb565(rgbbits[0])
                    rgb2 = decode_rgb565(rgbbits[1])
                    rgb_tween_bits = struct.unpack("<I", rawdata[i+0xC:i+0x10])[0]
                    x = y = 0
                    for j in range(16):
                        rgb_val = (rgb_tween_bits>>((j)*2))&0x3
                        if rgb_val == 0:
                            tween = 0
                        elif rgb_val == 1:
                            tween = 1
                        elif rgb_val == 2:
                            tween = 1/3
                        elif rgb_val == 3:
                            tween = 2/3
                        rgb = lerp_color(rgb1, rgb2, tween)
                        a_val = (alpha_tween_bits>>((j)*3))&0x7
                        if a_val == 0:
                            value = a1
                        elif a_val == 1:
                            value = a2
                        elif a_val == 2:
                            value = a1+(a2-a1)*(1/7)
                        elif a_val == 3:
                            value = a1+(a2-a1)*(2/7)
                        elif a_val == 4:
                            value = a1+(a2-a1)*(3/7)
                        elif a_val == 5:
                            value = a1+(a2-a1)*(4/7)
                        elif a_val == 6:
                            value = 0 if (a2 - a1) < 2 and (a2 - a1) >= 0 else a1+(a2-a1)*(5/7)
                        elif a_val == 7:
                            value = 1 if (a2 - a1) < 2 and (a2 - a1) >= 0 else a1+(a2-a1)*(6/7)
                            
                        if (tx+x) < mipwidth and (ty+y) < mipheight:
                            data[(((ty+y)*mipwidth)+(tx+x))*4:(((ty+y)*mipwidth)+(tx+x))*4+4] = [rgb[0], rgb[1], rgb[2], value]
                            
                        x+=1
                        if x >= 4:
                            x = 0
                            y+=1
                    tx+=4 
                    if tx >= mipwidth:
                        tx=0
                        ty+=4
            elif format_ == 0x34 or format_ == 0x234:
                data = [0 for i in range(mipwidth*mipheight*4)]
                tx = ty = 0
                for i in range(0, len(rawdata), 8):
                    if format_&0x200:
                        b1, b2 = rawdata[i:i+2]
                        b1+=0x80
                        if b1 >= 0x100: b1 -= 0x100
                        b2+=0x80
                        if b2 >= 0x100: b2 -= 0x100
                        v1 = b1/255
                        v2 = b2/255
                    else:
                        v1 = rawdata[i]/255
                        v2 = rawdata[i+1]/255
                    value_tween_bits = struct.unpack("Q", rawdata[i:i+8])[0] >> 16
                    x = y = 0
                    for j in range(16):
                        val = (value_tween_bits>>((j)*3))&0x7
                        if val == 0:
                            value = v1
                        elif val == 1:
                            value = v2
                        elif val == 2:
                            value = v1+(v2-v1)*(1/7)
                        elif val == 3:
                            value = v1+(v2-v1)*(2/7)
                        elif val == 4:
                            value = v1+(v2-v1)*(3/7)
                        elif val == 5:
                            value = v1+(v2-v1)*(4/7)
                        elif val == 6:
                            value = 0 if (v2 - v1) < 2 and (v2 - v1) >= 0 else v1+(v2-v1)*(5/7)
                        elif val == 7:
                            value = 1 if (v2 - v1) < 2 and (v2 - v1) >= 0 else v1+(v2-v1)*(6/7)
                            
                        if (tx+x) < mipwidth and (ty+y) < mipheight:
                            data[(((ty+y)*mipwidth)+(tx+x))*4:(((ty+y)*mipwidth)+(tx+x))*4+4] = [value, value, value, 1]
                            
                        x+=1
                        if x >= 4:
                            x = 0
                            y+=1
                    tx+=4 
                    if tx >= mipwidth:
                        tx=0
                        ty+=4
            elif format_ == 0x35 or format_ == 0x235:
                data = [0 for i in range(mipwidth*mipheight*4)]
                tx = ty = 0
                for i in range(0, len(rawdata), 16):
                    if format_&0x200:
                        xb1, xb2 = rawdata[i:i+2]
                        xb1+=0x80
                        if xb1 >= 0x100: xb1 -= 0x100
                        xb2+=0x80
                        if xb2 >= 0x100: xb2 -= 0x100
                        yb1, yb2 = rawdata[i+8:i+10]
                        yb1+=0x80
                        if yb1 >= 0x100: yb1 -= 0x100
                        yb2+=0x80
                        if yb2 >= 0x100: yb2 -= 0x100
                        xv1 = xb1/255
                        xv2 = xb2/255
                        yv1 = yb1/255
                        yv2 = yb2/255
                    else:
                        xv1 = rawdata[i]/255
                        xv2 = rawdata[i+1]/255
                        yv1 = rawdata[i+8]/255
                        yv2 = rawdata[i+9]/255
                    x_value_tween_bits = struct.unpack("Q", rawdata[i:i+8])[0] >> 16
                    
                    y_value_tween_bits = struct.unpack("Q", rawdata[i+8:i+16])[0] >> 16
                    
                    x = y = 0
                    for j in range(16):
                        x_val = (x_value_tween_bits>>((j)*3))&0x7
                        if x_val == 0:
                            x_value = xv1
                        elif x_val == 1:
                            x_value = xv2
                        elif x_val == 2:
                            x_value = xv1+(xv2-xv1)*(1/7)
                        elif x_val == 3:
                            x_value = xv1+(xv2-xv1)*(2/7)
                        elif x_val == 4:
                            x_value = xv1+(xv2-xv1)*(3/7)
                        elif x_val == 5:
                            x_value = xv1+(xv2-xv1)*(4/7)
                        elif x_val == 6:
                            x_value = 0 if (xv2 - xv1) < 2 and (xv2 - xv1) >= 0 else xv1+(xv2-xv1)*(5/7)
                        elif x_val == 7:
                            x_value = 1 if (xv2 - xv1) < 2 and (xv2 - xv1) >= 0 else xv1+(xv2-xv1)*(6/7)
                            
                        y_val = (y_value_tween_bits>>((j)*3))&0x7
                        if y_val == 0:
                            y_value = yv1
                        elif y_val == 1:
                            y_value = yv2
                        elif y_val == 2:
                            y_value = yv1+(yv2-yv1)*(1/7)
                        elif y_val == 3:
                            y_value = yv1+(yv2-yv1)*(2/7)
                        elif y_val == 4:
                            y_value = yv1+(yv2-yv1)*(3/7)
                        elif y_val == 5:
                            y_value = yv1+(yv2-yv1)*(4/7)
                        elif y_val == 6:
                            y_value = 0 if (yv2 - yv1) < 2 and (yv2 - yv1) >= 0 else yv1+(yv2-yv1)*(5/7)
                        elif y_val == 7:
                            y_value = 1 if (yv2 - yv1) < 2 and (yv2 - yv1) >= 0 else yv1+(yv2-yv1)*(6/7)
                            
                        if (tx+x) < mipwidth and (ty+y) < mipheight:
                            data[(((ty+y)*mipwidth)+(tx+x))*4:(((ty+y)*mipwidth)+(tx+x))*4+4] = [x_value, y_value, 1, 1]
                            
                        x+=1
                        if x >= 4:
                            x = 0
                            y+=1
                    tx+=4 
                    if tx >= mipwidth:
                        tx=0
                        ty+=4
            else: data = None
                                
            result = data
            if result == None:
                if operator is not None: operator.report({'ERROR'}, "Unrecognized texture format detected: %s in model %s" % (ftex.format_string()))
                print("\tError: Unrecognized texture format detected: %s in model %s" % (ftex.format_string()))
                return
            if pack:
                img = bpy.data.images.new(tname, mipwidth, mipheight, alpha=True)
                img.use_alpha = True
                img.alpha_mode = 'STRAIGHT'
                img.filepath = bpy.context.user_preferences.filepaths.temporary_directory+tname+".tga"
                img.file_format = 'TARGA'
            else:
                if img.source != 'GENERATED':
                    if operator is not None: operator.report({'ERROR'}, "Target image must be of a generated source.")
                    print("\tError: Target image must be of a generated source.")
                    return
                img.generated_width, img.generated_height = mipwidth, mipheight
            pixels = [0 for i in range(mipwidth*mipheight*4)]
            i = 0
            for y in range(mipheight-1, -1, -1):
                for x in range(mipwidth):
                    pixels[(y*mipwidth+x)*4:(y*mipwidth+x)*4+4] = result[i:i+4]
                    i+=4
            img.pixels[:] = pixels
            if pack:
                img.save()
                img.pack()
def get_tess_normal_by_vertex(mesh, vertex_id):
    r = find_vertex_from_face(mesh, vertex_id)
    if r is None: return (0,0,0)
    if r[1] >= len(mesh.tessfaces[r[0]].split_normals):
        return mesh.vertices[vertex_id].normal
    return mesh.tessfaces[r[0]].split_normals[r[1]][:]

def find_vertex_from_face(mesh, vertex_id):
    for pi in range(len(mesh.polygons)):
        for vi in range(len(mesh.polygons[pi].vertices)):
            if mesh.polygons[pi].vertices[vi] == vertex_id:
                return (pi,vi)

def SaveBFMDL_Mesh(fmdl, fmdlname, source_obj, operator = None):
    source_obj.data.calc_normals_split()
    source_obj.data.update(calc_edges=True, calc_tessface=True)
    
    if source_obj.type != 'MESH':
        if operator is not None: operator.report({'ERROR'}, "Source object is a mesh type.")
        print("\t\t\tError: Source object is a mesh type.")
        return
    
    numPolys = fmdl.get_polygon_count()
    if len(source_obj.material_slots) < numPolys:
        if operator is not None: operator.report({'ERROR'}, "The selected source object \"%s\" does not hold enough material slots. Please add in %i more slot(s)." % (source_obj.name, numPolys - len(source_obj.material_slots)))
        print("\t\t\tError: The selected source object \"%s\" does not hold enough material slots. Please add in %i more slot(s)." % (source_obj.name, numPolys - len(source_obj.material_slots)))
        return
    
    polygons = [[] for i in range(len(source_obj.material_slots))]
    
    vertex_indexes = [[] for i in range(len(source_obj.material_slots))]
    
    for p in source_obj.data.polygons:
        for pvi in range(len(p.vertices)-2):
            for v in [(p.vertices[0], p.loop_indices[0]), (p.vertices[pvi+1], p.loop_indices[pvi+1]), (p.vertices[pvi+2], p.loop_indices[pvi+2])]:
                if v not in vertex_indexes[p.material_index]:
                    vertex_indexes[p.material_index].append(v)
                polygons[p.material_index].append(vertex_indexes[p.material_index].index(v))
    
    for p in range(len(polygons)):
        if len(polygons[p]) == 0:
            polygons[p] = [0,0,0]
    
    #vertices = 
    #normals = [get_tess_normal_by_vertex(source_obj.data, vi) for vi in range(len(source_obj.data.vertices))]
    
    arm = None
    if "SKL_bind" in source_obj.modifiers:
        arm = source_obj.modifiers["SKL_bind"].object

    
    totalNumVerts = 0
    for j in range(numPolys):
        if j >= len(vertex_indexes): break
        print("\t\t\tImporting Polygon: %i of %i" % (j+1, numPolys))
        s = fmdl.get_polygon_data(j)
        s.get_LoD_model(0).skip_count(0)
        lod = s.get_LoD_model(min(fmdl.lod, s.LoD_model_count()))
        
        removeExtDatItems = []
        for extdatItem in bpy.context.scene.bfres.data.extra_data:
            if extdatItem["id"] == lod.offset:
                lod.get_buffer_offset(extdatItem["orig_data_offset"])
                lod.get_buffer_size(extdatItem["orig_data_size"])
                removeExtDatItems.append(extdatItem)
        for extdatItem in removeExtDatItems:
            bpy.context.scene.bfres.data.extra_data.remove(extdatItem)
        
        i_f = lod.index_format_string()
        bo = lod.get_buffer_offset()
        skip_count = lod.skip_count()
        size = lod.get_buffer_size()
        
        lod.visibility_group_count(1)
        lod.visibility_group_data_offset(0,0)
        lod.visibility_group_data_count(0,len(polygons[j]))
        
        o = bo
        stride = 0
        write_data = b''
        for bi in range(len(polygons[j])):
            value = polygons[j][bi]
            if i_f == "GX2_INDEX_FORMAT_U16":
                out_data = struct.pack(">H", value)
                stride=2
            else:
                if operator is not None: operator.report({'WARNING'}, "Unrecognized index format detected: %s in model %s" % (i_f, fmdlname))
                print("\t\t\tError: Unrecognized index format detected: %s in model %s" % (i_f, fmdlname))
                break
            write_data += out_data
        if len(write_data) >= size:
            pointers = []
            pointers.append({"pointer_offset": lod.index_buffer_offset()+0x14, "data_offset": 0})
            bpy.context.scene.bfres.data.extra_data.append({"id": lod.offset, "data": write_data, "orig_data_size": size, "orig_data_offset": bo, "pointers": pointers})
            lod.get_buffer_size(len(write_data))
        else:
            bpy.context.scene.bfres.data.bytes = bpy.context.scene.bfres.data.bytes[:bo] + write_data + bpy.context.scene.bfres.data.bytes[bo+len(write_data):]
        print("\t\t\tImporting Vertex Buffer: %i of %i" % (j+1, numPolys))
        v = FVTX(s.vertex_offset(), fmdl, bpy.context.scene.bfres.data)
        sm = s.vertex_skin_count()
        vertices = []
        normals = []
        uvs = [[],[],[],[]]
        colors = [[], []]
        weights = []
        indexes = []
        for k in range(v.attribute_count()):
            name = v.get_attribute_name(k)
            if name == "_p0":
                vertices = [source_obj.data.vertices[v[0]].co for v in vertex_indexes[j]]
                if arm is not None:
                    bpy.context.scene.objects.active = arm
                    bpy.ops.object.mode_set(mode='EDIT')
                    for vi, vii in zip(range(len(vertices)), vertex_indexes[j]):
                        if sm == 1:
                            for vg in source_obj.vertex_groups:
                                try:
                                    if vg.weight(vii[0]) >= 0.5:
                                        if vg.name in arm.data.edit_bones:
                                            vertices[vi] = arm.data.edit_bones[vg.name].matrix.inverted()*vertices[vi]
                                            break
                                except:
                                    None
                        elif sm >= 2:
                            vertices[vi] = flipYZ.inverted()*vertices[vi]
                    bpy.ops.object.mode_set(mode='OBJECT')
            elif name == "_n0":
                normals = [get_tess_normal_by_vertex(source_obj.data, vi[0]) for vi in vertex_indexes[j]]
                if arm is not None:
                    bpy.context.scene.objects.active = arm
                    bpy.ops.object.mode_set(mode='EDIT')
                    for vi, vii in zip(range(len(normals)), vertex_indexes[j]):
                        if sm == 1:
                            for vg in source_obj.vertex_groups:
                                try:
                                    if vg.weight(vii[0]) >= 0.5:
                                        if vg.name in arm.data.edit_bones:
                                            normals[vi] = arm.data.edit_bones[vg.name].matrix.inverted().to_3x3()*Vector(normals[vi])
                                            break
                                except:
                                    None
                        elif sm >= 2:
                            normals[vi] = flipYZ.inverted()*Vector(normals[vi])
                    bpy.ops.object.mode_set(mode='OBJECT')
            elif name == "_u0":
                if "Map1" in source_obj.data.uv_layers:
                    uvs[0] = [[source_obj.data.uv_layers["Map1"].data[v[1]].uv[0], 1 - source_obj.data.uv_layers["Map1"].data[v[1]].uv[1]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_u1":
                if "Map2" in source_obj.data.uv_layers:
                    uvs[1] = [[source_obj.data.uv_layers["Map2"].data[v[1]].uv[0], 1 - source_obj.data.uv_layers["Map2"].data[v[1]].uv[1]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_u2":
                if "Map3" in source_obj.data.uv_layers:
                    uvs[2] = [[source_obj.data.uv_layers["Map3"].data[v[1]].uv[0], 1 - source_obj.data.uv_layers["Map3"].data[v[1]].uv[1]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_u3":
                if "Map4" in source_obj.data.uv_layers:
                    uvs[3] = [[source_obj.data.uv_layers["Map4"].data[v[1]].uv[0], 1 - source_obj.data.uv_layers["Map4"].data[v[1]].uv[1]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_c0":
                if "Color1" in source_obj.data.vertex_colors and "Alpha1" in source_obj.data.vertex_colors:
                    colors[0] = [[source_obj.data.vertex_colors["Color1"].data[v[1]].color[0], source_obj.data.vertex_colors["Color1"].data[v[1]].color[1], source_obj.data.vertex_colors["Color1"].data[v[1]].color[2], source_obj.data.vertex_colors["Alpha1"].data[v[1]].color[0]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_c1":
                if "Color2" in source_obj.data.vertex_colors and "Alpha2" in source_obj.data.vertex_colors:
                    colors[1] = [[source_obj.data.vertex_colors["Color2"].data[v[1]].color[0], source_obj.data.vertex_colors["Color2"].data[v[1]].color[1], source_obj.data.vertex_colors["Color2"].data[v[1]].color[2], source_obj.data.vertex_colors["Alpha2"].data[v[1]].color[0]] for v in vertex_indexes[j]]
                else: continue
            elif name == "_w0":
                weights = []
                skl = fmdl.get_skeleton_data()
                for vi in vertex_indexes[j]:
                    vw = []
                    weight = [0,0,0,0]
                    for vg in source_obj.vertex_groups:
                        try:
                            vw.append(vg.weight(vi[0]))
                        except:
                            None
                    for mri in range(4):
                        if len(vw) == 0: break
                        mr = 0
                        for r in vw:
                            if r > mr:
                                mr = r
                        weight[mri] = mr
                        vw.remove(mr)
                    total_Weight = sum(weight)
                    if total_Weight>0:
                        for mrii in range(4):
                            weight[mrii] /= total_Weight
                    weights.append(weight)
            elif name == "_i0":
                indexes = []
                skl = fmdl.get_skeleton_data()
                for vi in vertex_indexes[j]:
                    vw = []
                    index = [0,0,0,0]
                    for vg in source_obj.vertex_groups:
                        try:
                            vw.append((vg.weight(vi[0]), vg.name))
                        except:
                            None
                    for mri in range(4):
                        if len(vw) == 0: break
                        mr = [0]
                        for r in vw:
                            if r[0] > mr[0]:
                                mr = r
                        if len(mr) == 1: continue
                        for bi in range(skl.num_bones()):
                            if skl.get_bone_name(bi) == mr[1]:
                                for bii in range(skl.num_bones()):
                                    if bi == skl.get_smooth_index(bii):
                                        index[mri] = bii
                                        break
                                break
                        vw.remove(mr)
                    indexes.append(index)
            else: print("\t\t\tUnsupported Type: " + name);
            
        for k in range(v.buffer_count()):
            prev_bytes_length = v.get_buffer_stride(k) * lod.skip_count()
            bo = v.get_buffer_offset(k)
            write_data = bpy.context.scene.bfres.data.bytes[bo:bo+prev_bytes_length]
            
            removeExtDatItems = []
            for extdatItem in bpy.context.scene.bfres.data.extra_data:
                if extdatItem["id"] == v.buffer_array_offset()+k*0x18:
                    v.get_buffer_offset(k, extdatItem["orig_data_offset"])
                    v.get_buffer_size(k, extdatItem["orig_data_size"])
                    removeExtDatItems.append(extdatItem)
            for extdatItem in removeExtDatItems:
                bpy.context.scene.bfres.data.extra_data.remove(extdatItem)
            
            bo = v.get_buffer_offset(k)
            size = v.get_buffer_size(k)
            for vi in range(max(len(vertices), len(normals), len(uvs[0]), len(uvs[1]), len(uvs[2]), len(uvs[3]), len(colors[0]), len(colors[1]), len(weights), len(indexes))):
                for l in range(v.attribute_count()):
                    va = v.get_attribute_data(l)
                    if va.buffer_index() != k: continue
                    name = v.get_attribute_name(l)
                    value = None
                    if name == "_p0":
                        if vi < len(vertices):
                            value = vertices[vi]
                    elif name == "_n0":
                        if vi < len(normals):
                            value = normals[vi]
                    elif name == "_u0":
                        if vi < len(uvs[0]):
                            value = uvs[0][vi]
                    elif name == "_u1":
                        if vi < len(uvs[1]):
                            value = uvs[1][vi]
                    elif name == "_u2":
                        if vi < len(uvs[2]):
                            value = uvs[2][vi]
                    elif name == "_u3":
                        if vi < len(uvs[3]):
                            value = uvs[3][vi]
                    elif name == "_c0":
                        if vi < len(colors[0]):
                            value = colors[0][vi]
                    elif name == "_c1":
                        if vi < len(colors[1]):
                            value = colors[1][vi]
                    elif name == "_w0":
                        if vi < len(weights):
                            value = weights[vi]
                    elif name == "_i0":
                        if vi < len(indexes):
                            value = indexes[vi]
                    
                    if value is not None:
                        fmt = va.format_string()
                        if fmt == "float_16_16_16_16":
                            x = numpy.float16(value[0]).byteswap().tobytes()
                            y = numpy.float16(value[1]).byteswap().tobytes()
                            z = numpy.float16(value[2]).byteswap().tobytes()
                            out_data = x+y+z+b'\0\0'
                        elif fmt == "float_16_16":
                            x = numpy.float16(value[0]).byteswap().tobytes()
                            y = numpy.float16(value[1]).byteswap().tobytes()
                            out_data = x+y
                        elif fmt == "float_32_32_32":
                            out_data = struct.pack(">3f", value[0], value[1], value[2])
                        elif fmt == "snorm_10_10_10_2":
                            out_data = _encode_3x_10bit_signed(value[2], value[1], value[0])
                        elif fmt == "snorm_16_16":
                            x, y = int(round(value[0]/2*0xffff)), int(round(value[1]/2*0xffff))
                            if x >= 0x8000: x -= 0x10000
                            if y >= 0x8000: y -= 0x10000
                            if min(x,y) < -0x8000 or max(x,y) >= 0x8000:
                                if operator is not None:
                                    operator.report({'ERROR'}, "Data value %s goes out of range -1.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    print("Data value %s goes out of range -1.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    return
                            out_data = struct.pack(">2h", x, y)
                        elif fmt == "uint_8":
                            out_data = struct.pack("B", value[0])
                        elif fmt == "uint_8_8":
                            out_data = struct.pack("BB", value[0], value[1])
                        elif fmt == "unorm_8_8":
                            out_data = struct.pack("BB", int(round(value[0]*255)), int(round(value[1]*255)))
                        elif fmt == "unorm_16_16":
                            x, y = int(round(value[0]*0xffff)), int(round(value[1]*0xffff))
                            if min(x,y) < 0x0 or max(x,y) >= 0x10000:
                                if operator is not None:
                                    operator.report({'ERROR'}, "Data value %s goes out of range 0.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    print("Data value %s goes out of range 0.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    return
                            out_data = struct.pack(">2H", x, y)
                        
                        elif fmt == "unorm_8_8_8_8":
                            if len(value) == 0:
                                a,b,c,d = 0,0,0,0
                            elif len(value) == 1:
                                a,b,c,d = int(round(value[0]*255)),0,0,0
                            elif len(value) == 2:
                                a,b,c,d = int(round(value[0]*255)),int(round(value[1]*255)),0,0
                            elif len(value) == 3:
                                a,b,c,d = int(round(value[0]*255)),int(round(value[1]*255)),int(round(value[2]*255)),0
                            else:
                                a,b,c,d = int(round(value[0]*255)),int(round(value[1]*255)),int(round(value[2]*255)),int(round(value[3]*255))
                            if min(a,b,c,d) < 0x0 or max(a,b,c,d) >= 0x100:
                                if operator is not None:
                                    operator.report({'ERROR'}, "Data value %s goes out of range 0.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    print("Data value %s goes out of range 0.0 to 1.0 in model %s, data type: %s" % (str(value), fmdlname, name));
                                    return
                            
                            out_data = struct.pack("BBBB", a,b,c,d)
                        elif fmt == "float_32_32":
                            out_data = struct.pack(">2f", value[0], value[1])
                        else:
                            if operator is not None: operator.report({'WARNING'}, "Unrecognized buffer format detected: %s in model %s" % (fmt, fmdlname))
                            print("\t\t\tError: Unrecognized buffer format detected: %s in model %s" % (fmt, fmdlname))
                            break
                    if vi == 0 and fmdl.lod == 0: va.buffer_offset(len(write_data))
                    write_data += out_data
                if vi == 0 and fmdl.lod == 0: v.get_buffer_stride(k, len(write_data))
            
            if len(write_data) >= size:
                pointers = []
                pointers.append({"pointer_offset": v.buffer_array_offset()+k*0x18+0x14, "data_offset": 0})
                bpy.context.scene.bfres.data.extra_data.append({"id": v.buffer_array_offset()+k*0x18, "data": write_data, "orig_data_size": size, "orig_data_offset": bo, "pointers": pointers})
                v.get_buffer_size(k, len(write_data))
            else:
                bpy.context.scene.bfres.data.bytes = bpy.context.scene.bfres.data.bytes[:bo] + write_data + bpy.context.scene.bfres.data.bytes[bo+len(write_data):]
            num_verts = int(ceil(len(write_data)/1.0/v.get_buffer_stride(k)))
            totalNumVerts += num_verts
            if (fmdl.lod+1) < s.LoD_model_count():
                s.get_LoD_model(fmdl.lod+1).skip_count(num_verts)
            
            v.num_vertices(num_verts)
    fmdl.total_num_vertices(totalNumVerts)
    bpy.context.scene.bfres.data.apply_extra_data()       
                
            
   
def LoadBFMDL_Mesh(fmdl, fmdlname, arm=None, target_obj=None, operator = None):
    print("\t\tImporting Vertex Buffers...")
    
    bm = bmesh.new()
    skl = fmdl.get_skeleton_data()
    numBones = skl.num_bones()
    
    _pcs = [0]
    ns = []
    uvls0 = []
    uvls1 = []
    uvls2 = []
    uvls3 = []
    vcs0 = []
    vcs1 = []
    wis = []
    whts = []
    for nv in range(fmdl.total_num_vertices()):
        bm.verts.new()
        uvls0.append((0,0))
        uvls1.append((0,0))
        uvls2.append((0,0))
        uvls3.append((0,0))
        vcs0.append((0,0,0))
        vcs1.append((0,0,0))
        ns.append((0,0,0))
        wis.append(None)
        whts.append(None)
    bm.verts.ensure_lookup_table()
    
    _vseek = 0
    numPolys = fmdl.get_polygon_count()
    for j in range(numPolys):
        print("\t\t\tImporting Vertex Buffer: %i of %i" % (j+1, numPolys))
        s = fmdl.get_polygon_data(j)
        v = FVTX(s.vertex_offset(), fmdl, bpy.context.scene.bfres.data)
        for k in range(v.attribute_count()):
            va = v.get_attribute_data(k)
            name = v.get_attribute_name(k)
            if name == "_p0": None
            elif name == "_n0": None
            elif name == "_u0":
                None
            elif name == "_u1":
                None
            elif name == "_u2":
                None
            elif name == "_u3":
                None
            elif name == "_c0":
                None
            elif name == "_c1":
                None
            elif name == "_i0":
                None
            elif name == "_w0":
                None
            else: print("\t\t\tUnsupported Type: " + name, "offset: "+hex(v.get_buffer_offset(va.buffer_index())+va.buffer_offset())); continue
            fmt = va.format_string()
            bo = v.get_buffer_offset(va.buffer_index())+va.buffer_offset()
            vd = []
            stride = v.get_buffer_stride(va.buffer_index())
            size = v.get_buffer_size(va.buffer_index())
            for vi in range(v.num_vertices()):
                o = bo + vi*stride
                if fmt == "float_32_32_32":
                    vd.append(struct.unpack(">3f", bpy.context.scene.bfres.data.bytes[o:o+0xC]))
                elif fmt == "float_16_16_16_16":
                    vd.append(numpy.frombuffer(bpy.context.scene.bfres.data.bytes[o:o+0x8 ], dtype=">4f2")[0].tolist())
                elif fmt == "snorm_16_16":
                    val = numpy.frombuffer(bpy.context.scene.bfres.data.bytes[o:o+0x4 ], dtype=">2h")[0].tolist()
                    val[0]/=0x7FFF
                    val[1]/=0x7FFF
                    vd.append(val)
                elif fmt == "unorm_16_16":
                    val = numpy.frombuffer(bpy.context.scene.bfres.data.bytes[o:o+0x4 ], dtype=">2H")[0].tolist()
                    val[0]/=0xFFFF
                    val[1]/=0xFFFF
                    vd.append(val)
                elif fmt == "float_32_32":
                    vd.append(numpy.frombuffer(bpy.context.scene.bfres.data.bytes[o:o+0x8 ], dtype=">2f")[0].tolist())
                elif fmt == "float_16_16":
                    vd.append(numpy.frombuffer(bpy.context.scene.bfres.data.bytes[o:o+0x4 ], dtype=">2f2")[0].tolist())
                elif fmt == "snorm_10_10_10_2":
                    vd.append(_parse_3x_10bit_signed(bpy.context.scene.bfres.data.bytes, o))
                elif fmt == "uint_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o],))
                elif fmt == "uint_8_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o],bpy.context.scene.bfres.data.bytes[o+1]))
                elif fmt == "uint_8_8_8_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o],bpy.context.scene.bfres.data.bytes[o+1],bpy.context.scene.bfres.data.bytes[o+2],bpy.context.scene.bfres.data.bytes[o+3]))
                elif fmt == "unorm_8_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o]/255.0,bpy.context.scene.bfres.data.bytes[o+1]/255.0))
                elif fmt == "snorm_8_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o]/255.0,bpy.context.scene.bfres.data.bytes[o+1]/255.0))
                elif fmt == "unorm_8_8_8_8":
                    vd.append((bpy.context.scene.bfres.data.bytes[o]/255.0,bpy.context.scene.bfres.data.bytes[o+1]/255.0,bpy.context.scene.bfres.data.bytes[o+2]/255.0,bpy.context.scene.bfres.data.bytes[o+3]/255.0))
                else:
                    if operator is not None: operator.report({'WARNING'}, "Unrecognized buffer format detected: %s in model %s" % (fmt, fmdlname))
                    print("\t\t\tError: Unrecognized buffer format detected: %s in model %s" % (fmt, fmdlname))
                    break
            if v.get_attribute_name(k) == "_p0":
                vi = 0
                for vtx in vd:
                    while len(vtx) < 3:
                        vtx.append(0)
                    _vseek = vi+_pcs[j]
                    bm.verts[_vseek].co = (vtx[0], vtx[1], vtx[2])
                    vi+=1
            if v.get_attribute_name(k) == "_n0":
                ni = 0
                for nml in vd:
                    while len(nml) < 3:
                        nml.append(0)
                    ns[ni + _pcs[j]] = (nml[2],nml[1],nml[0])
                    bm.verts[ni+_pcs[j]].normal = (nml[2],nml[1],nml[0])
                    ni+=1
            if v.get_attribute_name(k) == "_u0":
                ui = 0
                for uv in vd:
                    while len(uv) < 2:
                        uv.append(0)
                    uvls0[ui + _pcs[j]] = (uv[0], 1-uv[1])
                    ui += 1
            if v.get_attribute_name(k) == "_u1":
                ui = 0
                for uv in vd:
                    while len(uv) < 2:
                        uv.append(0)
                    uvls1[ui + _pcs[j]] = (uv[0], 1-uv[1])
                    ui += 1
            if v.get_attribute_name(k) == "_u2":
                ui = 0
                for uv in vd:
                    while len(uv) < 2:
                        uv.append(0)
                    uvls2[ui + _pcs[j]] = (uv[0], 1-uv[1])
                    ui += 1
            if v.get_attribute_name(k) == "_u3":
                ui = 0
                for uv in vd:
                    while len(uv) < 2:
                        uv.append(0)
                    uvls3[ui + _pcs[j]] = (uv[0], 1-uv[1])
                    ui += 1
            if v.get_attribute_name(k) == "_c0":
                ci = 0
                for color in vd:
                    while len(color) < 3:
                        color.append(0)
                    vcs0[ci + _pcs[j]] = (color[0], color[1], color[2])
                    ci += 1
            if v.get_attribute_name(k) == "_c1":
                ci = 0
                for color in vd:
                    while len(color) < 3:
                        color.append(0)
                    vcs1[ci + _pcs[j]] = (color[0], color[1], color[2])
                    ci += 1
            if v.get_attribute_name(k) == "_i0":
                wi = 0
                for wv in vd:
                    wis[wi + _pcs[j]] = wv
                    wi += 1
            if v.get_attribute_name(k) == "_w0":
                whi = 0
                for whv in vd:
                    whts[whi + _pcs[j]] = whv
                    whi += 1
        _pcs.append(_vseek+1)
    mi = []
    pmi = []
    print("\t\tImporting Polygons...")
    for j in range(numPolys):
        print("\t\t\tImporting Polygon: %i of %i" % (j+1, numPolys))
        s = fmdl.get_polygon_data(j)
        lod = s.get_LoD_model(min(fmdl.lod, s.LoD_model_count()))
        pt = lod.primitive_type_string()
        i_f = lod.index_format_string()
        bo = lod.get_buffer_offset()
        skip_count = lod.skip_count()
        id = []
        size = lod.get_buffer_size()
        stride = 0
        if i_f == "GX2_INDEX_FORMAT_U16":
            stride = 2
            
        for vis_grp in range(lod.visibility_group_count()):
            offset = lod.visibility_group_data_offset(vis_grp)
            for bi in range(lod.visibility_group_data_count(vis_grp)):
                o = bo + offset + bi * stride
                if i_f == "GX2_INDEX_FORMAT_U16":
                    id.append(struct.unpack(">H", bpy.context.scene.bfres.data.bytes[o:o+2])[0]+skip_count)
                else:
                    if operator is not None: operator.report({'WARNING'}, "Unrecognized index format detected: %s in model %s" % (i_f, fmdlname))
                    print("\t\t\tError: Unrecognized index format detected: %s in model %s" % (i_f, fmdlname))
                    break
        _tri = []
        for index in id:
            if pt == "GX2_PRIMITIVE_TRIANGLES":
                _tri.append(index)
                if len(_tri) == 3:
                    try:
                        face = bm.faces.new((bm.verts[_tri[0]+_pcs[j]],bm.verts[_tri[1]+_pcs[j]],bm.verts[_tri[2]+_pcs[j]]))
                        face.smooth = True
                        mi.append(j)
                    except:
                        None
                    _tri = []
            else:
                if operator is not None: operator.report({'WARNING'}, "Unrecognized primitive type detected: %s in model %s" % (pt, fmdlname))
                print("\t\t\tError: Unrecognized primitive type detected: %s in model %s" % (pt, fmdlname))
                break
        pmi.append(s.material_index())
    
    bm.faces.ensure_lookup_table()
    
    if target_obj is None:
        if fmdlname in bpy.data.meshes:
            bpy.data.meshes.remove(bpy.data.meshes[fmdlname])
        m = bpy.data.meshes.new(fmdlname)
    else: m = target_obj.data
    
    bm.to_mesh(m)
    
    uvtt0 = m.uv_textures.new("Map1")
    uvtl0 = m.uv_layers["Map1"]
    uvtt1 = m.uv_textures.new("Map2")
    uvtl1 = m.uv_layers["Map2"]
    uvtt2 = m.uv_textures.new("Map3")
    uvtl2 = m.uv_layers["Map3"]
    uvtt3 = m.uv_textures.new("Map4")
    uvtl3 = m.uv_layers["Map4"]
    color_map0 = m.vertex_colors.new("Color1")
    color_alpha0 = m.vertex_colors.new("Alpha1")
    color_map1 = m.vertex_colors.new("Color2")
    color_alpha1 = m.vertex_colors.new("Alpha2")
    for p in m.polygons:
        for vi in range(len(p.loop_indices)):
            uvtl0.data[p.loop_indices[vi]].uv = uvls0[p.vertices[vi]]
            uvtl1.data[p.loop_indices[vi]].uv = uvls1[p.vertices[vi]]
            uvtl2.data[p.loop_indices[vi]].uv = uvls2[p.vertices[vi]]
            uvtl3.data[p.loop_indices[vi]].uv = uvls3[p.vertices[vi]]
            color_map0.data[p.loop_indices[vi]].color = vcs0[p.vertices[vi]]
            color_alpha0.data[p.loop_indices[vi]].color = (vcs0[p.vertices[vi]][3],vcs0[p.vertices[vi]][3],vcs0[p.vertices[vi]][3]) if len(vcs0[p.vertices[vi]]) >= 4 else (1,1,1)
            color_map1.data[p.loop_indices[vi]].color = vcs1[p.vertices[vi]]
            color_alpha1.data[p.loop_indices[vi]].color = (vcs1[p.vertices[vi]][3],vcs1[p.vertices[vi]][3],vcs1[p.vertices[vi]][3]) if len(vcs1[p.vertices[vi]]) >= 4 else (1,1,1)
    
    
    
    
    #Importing Materials
    print("\t\tImporting Materials...")
    mats = []
    numMaterials = fmdl.get_material_count()
    for mt in range(numMaterials):
        inmat = fmdl.get_material_data(mt)
        mname = fmdlname+"/"+fmdl.get_material_name(mt)
        print("\t\t\tImporting Material: %s\t\t%i of %i" % (mname, mt+1, numMaterials))
        if mname in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[mname])
        outmat = bpy.data.materials.new(mname)
        if bpy.context.scene.render.engine == "CYCLES":
            outmat.use_nodes = True
            nt = outmat.node_tree
            for tpi in range(inmat.texture_param_count()):
                tpname = inmat.get_texture_param_name(tpi)
                tp = inmat.get_texture_param_data(tpi)
                index = tp.index()
                if tpname == "_a0":
                    img_node = nt.nodes.new('ShaderNodeTexImage')
                    img_node.image = bpy.data.images.get(inmat.get_texture_name(index))
                    nt.links.new(img_node.outputs[0], nt.nodes["Diffuse BSDF"].inputs[0])
                    mix_shader_node = nt.nodes.new('ShaderNodeMixShader')
                    transparent_shader_node = nt.nodes.new('ShaderNodeBsdfTransparent')
                    nt.links.new(img_node.outputs[1], mix_shader_node.inputs[0])
                    nt.links.new(transparent_shader_node.outputs[0], mix_shader_node.inputs[1])
                    nt.links.new(nt.nodes["Diffuse BSDF"].outputs[0], mix_shader_node.inputs[2])
                    nt.links.new(mix_shader_node.outputs[0], nt.nodes["Material Output"].inputs[0])
        else:
            outmat.diffuse_color.s = random()*0.5+0.5
            outmat.diffuse_color.v = random()*0.125+0.875
            h = random()
            outmat.diffuse_color.h = h
            for tpi in range(inmat.texture_param_count()):
                tpname = inmat.get_texture_param_name(tpi)
                tp = inmat.get_texture_param_data(tpi)
                index = tp.index()
                imgname = inmat.get_texture_name(index)
                img = bpy.data.images.get(imgname)
                ts = outmat.texture_slots.add()
                if mname+"/"+imgname in bpy.data.textures:
                    bpy.data.textures.remove(bpy.data.textures[mname+"/"+imgname])
                ts.texture = bpy.data.textures.new(mname+"/"+imgname, 'IMAGE')
                ts.texture.image = img
        mats.append(outmat)
    
    
    if target_obj is not None:
        m.materials.clear()
    
    
    for pmii in pmi:
        m.materials.append(mats[pmii])
    
    
    for pi in range(len(m.polygons)):
        m.polygons[pi].material_index = mi[pi]
        if m.materials[mi[pi]].texture_slots[0] is not None:
            if m.materials[mi[pi]].texture_slots[0].texture is not None:
                uvtt0.data[pi].image = m.materials[mi[pi]].texture_slots[0].texture.image
    #vc = m.vertex_colors.new("normTest")
    #v = 0
    #for t in bm.faces:
    #    for l in t.loops:
    #        vc.data[v].color[0] = l.vert.normal[0]
    #        vc.data[v].color[1] = l.vert.normal[1]
    #        vc.data[v].color[2] = l.vert.normal[2]
    #        v+=1
    if target_obj is None:
        if fmdlname in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[fmdlname])
        o = bpy.data.objects.new(fmdlname, m)
    else:
        target_obj.vertex_groups.clear()
        o = target_obj
    for k in range(numBones): o.vertex_groups.new(skl.get_bone_name(k))
    o.modifiers.clear()
    o.modifiers.new("SKL_bind", 'ARMATURE').object = arm
    
    print("\t\tBinding Vertices to Bones...")
    for iii in range(_pcs[len(_pcs)-1]):
        iik = 0
        for iij in range(1, len(_pcs)):
            if iii >= _pcs[iij-1] and iii < _pcs[iij]:
                break
            iik+=1
        s = fmdl.get_polygon_data(iik)
        sm = s.vertex_skin_count()
        if sm == 0:
            bone_index = s.skeleton_index()
            bname = skl.get_bone_name(bone_index, True)
            o.vertex_groups[bname].add((iii,), 1, 'ADD')
            if arm is not None:
                bpy.context.scene.objects.active = arm
                bpy.ops.object.mode_set(mode='EDIT')
                if bname not in arm.data.edit_bones: continue
                mtx = arm.data.edit_bones[bname].matrix
                bpy.ops.object.mode_set(mode='OBJECT')
                m.vertices[iii].co = mtx*m.vertices[iii].co
                m.vertices[iii].normal = mtx.to_3x3()*m.vertices[iii].normal
                ns[iii] = (mtx.to_3x3()*Vector(ns[iii])).to_tuple()
        elif sm == 1:
            bone_index = skl.get_smooth_index(wis[iii][0])
            bname = skl.get_bone_name(bone_index)
            o.vertex_groups[bname].add((iii,), 1, 'ADD')
            if arm is not None:
                bpy.context.scene.objects.active = arm
                bpy.ops.object.mode_set(mode='EDIT')
                if bname not in arm.data.edit_bones: continue
                mtx = arm.data.edit_bones[bname].matrix
                bpy.ops.object.mode_set(mode='OBJECT')
                m.vertices[iii].co = mtx*m.vertices[iii].co
                m.vertices[iii].normal = mtx.to_3x3()*m.vertices[iii].normal
                ns[iii] = (mtx.to_3x3()*Vector(ns[iii])).to_tuple()
        elif sm >= 2:
            for w in range(sm):
                bone_index = skl.get_smooth_index(wis[iii][w])
                bname = skl.get_bone_name(bone_index)
                o.vertex_groups[bname].add((iii,), whts[iii][w], 'ADD')
            m.vertices[iii].co = flipYZ*m.vertices[iii].co
            m.vertices[iii].normal = flipYZ.to_3x3()*m.vertices[iii].normal
            ns[iii] = (flipYZ.to_3x3()*Vector(ns[iii])).to_tuple()
    
    print("\t\tFinalizing Model...")
    m.use_auto_smooth = True
    nms = []
    for n in ns:
        nms.append(Vector(n).normalized())
    
    m.normals_split_custom_set_from_vertices(nms)
    
    if target_obj is None: bpy.context.scene.objects.link(o)
def SaveBFMDL_Skeleton(fmdl, fmdlname, arm, operator=None):
    if arm.type != 'ARMATURE':
        if operator is not None: operator.report({'ERROR'}, "Source object is an armature type.")
        print("\t\t\tError: Source object is an armature type.")
        return
    skl = fmdl.get_skeleton_data()
    bpy.context.scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for i in range(len(arm.data.edit_bones)):
        bfskl_bone_name = skl.get_bone_name(i)
        bfskl_bone_data = skl.get_bone_data(i)
        if bfskl_bone_name != arm.data.edit_bones[i].name:
            if operator is not None:
                operator.report({'WARNING'}, "Bone name mismatch: Armature bone: %s, BFMDL bone: %s." % (arm.data.edit_bones[i].name, bfskl_bone_name))
                print("\tBone name mismatch: Armature bone: %s, BFMDL bone: %s." % (arm.data.edit_bones[i].name, bfskl_bone_name))
        mtx = arm.data.edit_bones[i].matrix
        mtx = flipYZ.inverted()*mtx
        b = arm.data.edit_bones[i].parent
        if b is not None:
            mtx = flipMtx(flipMtx(mtx)*flipMtx(flipYZ.inverted()*b.matrix).inverted())
        pos = mtx.to_translation()
        if bfskl_bone_data.uses_euler():
            rot = mtx.to_euler()
            rot = (rot[0], rot[1], rot[2], 1)
        else:
            rot = mtx.to_quaternion()
            rot = (rot[1],rot[2],rot[3], rot[0])
        scl = mtx.to_scale()
        
        print(bfskl_bone_name)
        print(bfskl_bone_data.translation_vector(), bfskl_bone_data.rotation_vector(), bfskl_bone_data.scale_vector())
        bfskl_bone_data.translation_vector(pos)
        bfskl_bone_data.rotation_vector(rot)
        bfskl_bone_data.scale_vector(scl)
        print(bfskl_bone_data.translation_vector(), bfskl_bone_data.rotation_vector(), bfskl_bone_data.scale_vector())
        
    bpy.ops.object.mode_set(mode='OBJECT') 

def LoadBFMDL_Skeleton(fmdl, fmdlname, arm=None, operator=None):
    skl = fmdl.get_skeleton_data()
    if arm is None:
        if fmdlname+"_armature" in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[fmdlname+"_armature"])
        if fmdlname+"_armature" in bpy.data.armatures:
            bpy.data.armatures.remove(bpy.data.armatures[fmdlname+"_armature"])
        arm = bpy.data.objects.new(fmdlname+"_armature", bpy.data.armatures.new(fmdlname+"_armature"))
    
        bpy.context.scene.objects.link(arm)
    else:
        bpy.context.scene.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        while len(arm.data.edit_bones) != 0: arm.data.edit_bones.remove(arm.data.edit_bones[0])
        bpy.ops.object.mode_set(mode='OBJECT') 
    bpy.context.scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    print("\t\tImporting Bones...")
    numBones = skl.num_bones()
    for k in range(numBones):
        bn = arm.data.edit_bones.new(skl.get_bone_name(k))
        print("\t\t\tImporting Bone: %s\t\t%i of %i" % (bn, k+1, numBones))
        src_bn = skl.get_bone_data(k)
        pos = src_bn.translation_vector()
        rot = src_bn.rotation_vector() 
        scl = src_bn.scale_vector()
        bn.tail = bn.head + Vector((0,0,1))
        bn.matrix = matrix_from_transform(Vector((pos[0], pos[1], pos[2])), Euler(((rot[0]), (rot[1]), (rot[2]))) if src_bn.uses_euler() else Quaternion((rot[3], rot[0], rot[1], rot[2])), (scl[0], scl[1], scl[2]))
        pb = skl.get_bone_data(src_bn.parent_index())
        
        while pb is not None:
            pos = pb.translation_vector()
            rot = pb.rotation_vector()
            scl = pb.scale_vector()
            bn.matrix = flipMtx(flipMtx(bn.matrix) * flipMtx(matrix_from_transform(Vector((pos[0], pos[1], pos[2])),  Euler(((rot[0]), (rot[1]), (rot[2]))) if pb.uses_euler() else Quaternion((rot[3], rot[0], rot[1], rot[2])), (scl[0], scl[1], scl[2]))))
            pb = skl.get_bone_data(pb.parent_index())
        bn.matrix = flipYZ*bn.matrix
        
    
    print("\t\tParenting Bones...")
    for k in range(numBones):
        bn = arm.data.edit_bones[skl.get_bone_name(k)]
        src_bn = skl.get_bone_data(k)
        pi = src_bn.parent_index()
        if skl.get_bone_name(pi) is not None: bn.parent = arm.data.edit_bones[skl.get_bone_name(pi)]
    bpy.ops.object.mode_set(mode='OBJECT')  
    return arm 
            
class LoadBFRESToScene(bpy.types.Operator):
    """Loads the BFRES file into scene"""
    bl_idname = "scene.loadbfres"
    bl_label = "Load to Scene"

    @classmethod
    def poll(cls, context):
        return context.scene.bfres.data is not None and len(context.scene.objects) == 0

    def execute(self, context):
        if(context.scene.bfres.data.magic() != b'FRES'):
            self.report({'ERROR'}, "Not a BFRES file.")
            print("Error: Not a BFRES file.")
            return {'CANCELLED'}
        numTextures = context.scene.bfres.data.texture_index_group_count()
        print("Importing Textures...")
        for i in range(numTextures):
            ftex = context.scene.bfres.data.get_texture_data(i)
            tname = context.scene.bfres.data.get_texture_name(i)
            print("\tImporting Texture: %s\t\t%i of %i" % (tname, i+1, numTextures))
            LoadBFTEX(ftex, tname, 0, pack=True, operator=self)

        print("Importing Models...")
        numModels = context.scene.bfres.data.model_index_group_count()
        for i in range(numModels):
            fmdl = context.scene.bfres.data.get_model_data(i)
            fmdlname = context.scene.bfres.data.get_model_name(i)
            print("\tImporting Model: %s\t\t%i of %i" % (fmdlname, i+1, numModels))
            #Importing Skeleton
            arm = LoadBFMDL_Skeleton(fmdl, fmdlname, operator=self)
                         
            
            #Importing Models
            LoadBFMDL_Mesh(fmdl, fmdlname, arm=arm, operator=self)
                
        return {'FINISHED'}



class ImportBFRES(Operator, ImportHelper):
    """Fills the current scene with the contents of the imported BFRES file"""
    bl_idname = "scene.import_bfres"
    bl_label = "Import BFRES"

    filename_ext = ".bfres"

    filter_glob = StringProperty(
            default="*.bfres",
            options={'HIDDEN'},
            maxlen=255,
            )
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        context.scene.bfres.data = BFRES(self.filepath)
        print("BFRES Loaded.")
        return {'FINISHED'}

class FindWiiUIP(bpy.types.Operator):
    """Finds the Wii U's IP address"""
    bl_idname = "scene.findwiiu"
    bl_label = "Find Wii U"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        hostname = socket.gethostname()   
        IPAddr = socket.gethostbyname(hostname)
        print("Your ip address is:", IPAddr)
        IPAddrBase = IPAddr
        while not IPAddrBase.endswith(".") and len(IPAddrBase) > 0: IPAddrBase = IPAddrBase[:-1]
        print("Searching for Wii U...")
        WiiU_Found = False
        context.scene.tcp_gecko_IP = ""
        for i in range(0, 255):
            tryIP = IPAddrBase+str(i)
            print("Trying IP:\t"+tryIP)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            try:
                s.connect((tryIP, 7331))
            except:
                print("Failed.")
                continue
            s.close()
            print("Found Wii U. IP address: ", tryIP)
            context.scene.tcp_gecko_IP = tryIP
            WiiU_Found = True
            break
        if not WiiU_Found:
            self.report({'ERROR'}, "Could not find Wii U.")
        return {'FINISHED'}

class ConnectToWiiU(bpy.types.Operator):
    """Connect to the Wii U"""
    bl_idname = "scene.connectwiiu"
    bl_label = "Connect to Wii U"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global sock, tcpGecko
        print("Connecting to Wii U...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((context.scene.tcp_gecko_IP, 7331))
        except:
            sock = None
            print("Failed to connect to Wii U.")
            self.report({'ERROR'}, "Failed to connect to Wii U.")
            return {'CANCELLED'}
        tcpGecko = TCPGecko(sock)
        #print(hex(tcpGecko.data_mem), hex(tcpGecko.data_mem+tcpGecko.data_mem_size))
        
        print("Successfully connected to Wii U.")
        return {'FINISHED'}

class DisconnectWiiU(bpy.types.Operator):
    """Disconnect from the Wii U"""
    bl_idname = "scene.disconnectwiiu"
    bl_label = "Disonnect Wii U"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global sock, tcpGecko, TCPBFRESLIST, currentDownloadedID
        TCPBFRESLIST = []
        currentDownloadedID = None
        sock.close()
        sock = None
        tcpGecko = None
        print("Disconnected from Wii U.")
        return {'FINISHED'}

class GetBFRESList(bpy.types.Operator):
    """Search for every BFRES file in memory and list the results"""
    bl_idname = "scene.getbfreslist"
    bl_label = "Find all BFRES"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global sock, tcpgecko, TCPBFRESLIST, currentDownloadedID
        TCPBFRESLIST = []
        currentDownloadedID = None
        print("Fetching free memory in Wii U to process list...")
        address = tcpGecko.call(tcpGeckoFunctions['findFreeSpace'], 0x2000, 0xA000, tcpGecko.data_mem, tcpGecko.data_mem_size)
        if(address == 0):
            self.report({'ERROR'}, "Not enough free space in Wii U memory to process list.")
            return {'CANCELLED'}
        print("Searching for all BFRES headers...")
        sock.settimeout(30)
        tcpGecko.call(tcpGeckoFunctions['find_bfres_headers'], address, tcpGecko.data_mem, tcpGecko.data_mem_size)
        sock.settimeout(5)
        print("Downloading results...")
        resultdata = tcpGecko.readmem(address, 0x8000, True)
        print("Cleaning up...")
        tcpGecko.call(tcpGeckoFunctions['clearMemory'], address, 0x8000)
        print("Importing results...")
        for seek in range(0, 0x8000, 0x20):
            currentresultdata = resultdata[seek:seek+0x20]
            BFRESaddress, BFRESsize = struct.unpack(">II", currentresultdata[:8])
            if BFRESaddress == 0: break
            for namelen in range(0x1C):
                if currentresultdata[8+namelen] == 0: break
            name = currentresultdata[8:8+namelen].decode("UTF-8")
            TCPBFRESLIST.append((BFRESaddress, BFRESsize, name))
        return {'FINISHED'}

class DownloadBFRES(bpy.types.Operator):
    """Downloads the selected BFRES model"""
    bl_idname = "scene.downloadbfres"
    bl_label = "Download"
    
    id = IntProperty()
    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global sock, tcpGecko, TCPBFRESLIST, currentDownloadedID
        print("Downloading BFRES...")
        address = TCPBFRESLIST[self.id][0]
        size = TCPBFRESLIST[self.id][1]
        context.scene.bfres.data = BFRES(None, tcpGecko.readmem(address, size))
        currentDownloadedID = self.id
        print("BFRES downloaded.")
        return {'FINISHED'}
class RestoreBFRES(bpy.types.Operator):
    """Restores the BFRES back to where it was last saved/opened"""
    bl_idname = "scene.restorebfres"
    bl_label = "Restore BFRES"
    
    @classmethod
    def poll(cls, context):
        return context.scene.bfres.data is not None

    def execute(self, context):
        context.scene.bfres.data.bytes = context.scene.bfres.data.orig_bytes
        return {'FINISHED'}
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class SaveBFRESToFile(bpy.types.Operator, ExportHelper):
    """Saves the BFRES to file"""
    bl_idname = "scene.savebfrestofile"
    bl_label = "Save BFRES"
    
    filename_ext = ".bfres"
    
    @classmethod
    def poll(cls, context):
        return context.scene.bfres.data is not None

    def execute(self, context):
        f = open(self.filepath, "wb")
        f.write(context.scene.bfres.data.bytes)
        f.close()
        context.scene.bfres.data.orig_bytes = context.scene.bfres.data.bytes
        return {'FINISHED'}
    
class SaveBFRESToFilePatches(bpy.types.Operator, ExportHelper):
    """Saves the BFRES to a file patch for SD Cafiine Plus"""
    bl_idname = "scene.savebfrestofilepatch"
    bl_label = "Save to File Patch"
    
    in_decompression_hook = BoolProperty(name="In Decompression Hook")
    offset_bias = IntProperty(name="Offset Bias", min=0)
    extra_data_bias = IntProperty(name="Extra Data Offset Bias", min=0)
    filename_ext = ""
    
    @classmethod
    def poll(cls, context):
        return context.scene.bfres.data is not None

    def execute(self, context):
        patches = {}
        patch_start = -1
        same_count = 0
        patch_end = -1
        dirpath, filename = os.path.split(self.filepath)
        filesize = len(context.scene.bfres.data.orig_bytes)
        patchdir = hex(hash(filename)%(0x10**8))[2:]
        for i in range(filesize):
            oldB, newB = context.scene.bfres.data.orig_bytes[i], context.scene.bfres.data.bytes[i]
            if oldB!=newB:
                if (same_count <= 0):
                    patch_start = i
                if (patch_end - patch_start) < 0x40: same_count = 0x4
                else: same_count = 0x40
                patch_end = i+1
            else:
                same_count -= 1
                if(same_count <= 0) and patch_start != -1:
                    patches[patch_start+self.offset_bias] = context.scene.bfres.data.bytes[patch_start:patch_end]
                    patch_start = -1
        AddBytes = 0
        for extra_data in context.scene.bfres.data.extra_data:
            patches[filesize+AddBytes+self.extra_data_bias] = extra_data["data"]
            for pointer in extra_data["pointers"]:
                for pi in range(4):
                    if pi+pointer["pointer_offset"] in patches:
                        del patches[pi+pointer["pointer_offset"]]
                patches[pointer["pointer_offset"]] = struct.pack(">i", pointer["data_offset"]+filesize+AddBytes+self.extra_data_bias-pointer["pointer_offset"])
            AddBytes += len(extra_data["data"])
        XML = ""
        if AddBytes > 0:
            XML += "<resize length=\"%s\" />\n" % hex(filesize+AddBytes)
        for patch in sorted(patches):
            p = patches[patch]
            if len(p) < 0x40:
                pp = p
                while len(pp) > 0:
                    ppp = len(p) - len(pp)
                    if len(pp) == 1:
                        XML += "<ubyte offset=\"%s\"><set value=\"%s\"/></ubyte>\n" % (hex(patch + ppp), hex(pp[0]))
                        pp = pp[1:]
                    elif len(pp) == 2:
                        XML += "<ushort offset=\"%s\"><set value=\"%s\"/></ushort>\n" % (hex(patch + ppp), hex(struct.unpack(">H", pp[:2])[0]))
                        pp = pp[2:]
                    elif len(pp) == 3:
                        XML += "<ubyte offset=\"%s\"><set value=\"%s\"/></ubyte><ubyte offset=\"%s\"><set value=\"%s\"/></ubyte><ubyte offset=\"%s\"><set value=\"%s\"/></ubyte>\n" % (hex(patch + ppp), hex(pp[0]),hex(patch+1 + ppp), hex(pp[1]),hex(patch+2 + ppp), hex(pp[2]))
                        pp = pp[3:]
                    else:
                        XML += "<uint offset=\"%s\"><set value=\"%s\"/></uint>\n" % (hex(patch + ppp), hex(struct.unpack(">I", pp[:4])[0]))
                        pp = pp[4:]
            else:
                fill = True
                prevPB = None
                for PB in p:
                    if prevPB is None:
                        prevPB = PB
                    elif prevPB!=PB:
                        fill = False
                        break
                if fill:
                    XML += "<ubyte offset=\"%s\"><fill value=\"%s\" size=\"%s\"/></ubyte>\n" % (hex(patch), hex(p[0]), hex(len(p)))
                else:
                    if not os.path.exists(dirpath+"/"+patchdir): os.mkdir(dirpath+"/"+patchdir)
                    patchdatafilepath = patchdir+"/"+(hex(patch)[2:])
                    if len(patchdatafilepath) > 0x16:
                        patchdatafilepath = patchdatafilepath[:0x16]+"_"
                    patchdatafilepath += ".bin"
                    patchdatafile = open(dirpath+"/"+patchdatafilepath, "wb")
                    patchdatafile.write(p)
                    patchdatafile.close()
                    XML += "<fileInject offset=\"%s\" src=\"%s\"/>\n" % (hex(patch), patchdatafilepath)
        if self.in_decompression_hook:
            copy(XML)
            self.report({'INFO'}, "XML data was copied to your clipboard. Paste this into the decompression hook in globalPatches.xml.")
        else:
            XMLFile = open(self.filepath+".patch.xml", "w")
            XMLFile.write(XML)
            XMLFile.close()
        return {'FINISHED'}

class ShowHideBFTEXTools(bpy.types.Operator):
    """Shows or hides the tools for BFTEX textures"""
    bl_idname = "scene.showhidebftextools"
    bl_label = "show or hide"
    
    bftex_id = StringProperty()

    def execute(self, context):
        context.scene.bfres.data.textures[self.bftex_id].display_info = not context.scene.bfres.data.textures[self.bftex_id].display_info
        return {'FINISHED'}
class ShowHideBFMDLTools(bpy.types.Operator):
    """Shows or hides the tools for BFMDL models"""
    bl_idname = "scene.showhidebfmdltools"
    bl_label = "show or hide"
    
    bfmdl_id = StringProperty()

    def execute(self, context):
        context.scene.bfres.data.models[self.bfmdl_id].display_info = not context.scene.bfres.data.models[self.bfmdl_id].display_info
        return {'FINISHED'}
class ActiveObjectToTarget(bpy.types.Operator):
    """Sets the target to the active object"""
    bl_idname = "scene.bfmdlaototarget"
    bl_label = ""

    def execute(self, context):
        context.scene.bfmdl_target_model = context.active_object.name
        return {'FINISHED'}
class ActiveObjectToSource(bpy.types.Operator):
    """Sets the source to the active object"""
    bl_idname = "scene.bfmdlaotosource"
    bl_label = ""

    def execute(self, context):
        context.scene.bfmdl_source_model = context.active_object.name
        return {'FINISHED'}
class ActiveObjectToTargetArmature(bpy.types.Operator):
    """Sets the target armature to the active object"""
    bl_idname = "scene.bfmdlaototargetarmature"
    bl_label = ""

    def execute(self, context):
        context.scene.bfmdl_target_armature = context.active_object.name
        return {'FINISHED'}
class ActiveObjectToSourceArmature(bpy.types.Operator):
    """Sets the source armature to the active object"""
    bl_idname = "scene.bfmdlaotosourcearmature"
    bl_label = ""

    def execute(self, context):
        context.scene.bfmdl_source_armature = context.active_object.name
        return {'FINISHED'}
class DecreaseLod(bpy.types.Operator):
    """Decreases the current lod of the model"""
    bl_idname = "scene.bfmdlloddown"
    bl_label = ""
    
    bfmdl_id = StringProperty()

    def execute(self, context):
        context.scene.bfres.data.models[self.bfmdl_id].lod-=1
        if context.scene.bfres.data.models[self.bfmdl_id].lod < 0:
            context.scene.bfres.data.models[self.bfmdl_id].lod = 0
        return {'FINISHED'}
class IncreaseLod(bpy.types.Operator):
    """Increases the current lod of the model"""
    bl_idname = "scene.bfmdllodup"
    bl_label = ""
    
    bfmdl_id = StringProperty()

    def execute(self, context):
        lod_count = 0
        for pname in context.scene.bfres.data.models[self.bfmdl_id].polygons:
            lod_count = max(lod_count, context.scene.bfres.data.models[self.bfmdl_id].polygons[pname].LoD_model_count())
        if lod_count-1 > context.scene.bfres.data.models[self.bfmdl_id].lod:
            context.scene.bfres.data.models[self.bfmdl_id].lod+=1
        return {'FINISHED'}
class LoadBFMDLSkeletontoScene(bpy.types.Operator):
    """Loads the BFMDL skeleton into the target blender object's armature"""
    bl_idname = "scene.exportbfmdlskeleton"
    bl_label = "Load Skeleton"
    
    bfmdl_id = StringProperty()
    
    
    def execute(self, context):
        if context.scene.bfmdl_target_model+"_armature" not in context.scene.objects:
            context.scene.bfmdl_target_armature = self.bfmdl_id+"_armature"
            arm = bpy.data.armatures.new(self.bfmdl_id+"_armature")
            obj = bpy.data.objects.new(self.bfmdl_id+"_armature", arm)
            context.scene.objects.link(obj)
        else: obj = context.scene.objects[context.scene.bfmdl_target_armature]
        LoadBFMDL_Skeleton(context.scene.bfres.data.models[self.bfmdl_id], self.bfmdl_id, arm = context.scene.objects.get(context.scene.bfmdl_target_armature), operator=self)
        return {'FINISHED'}
class SaveBFMDLSkeletonfromScene(bpy.types.Operator):
    """Writes into the BFMDL skeleton data from the source blender object's armature"""
    bl_idname = "scene.importbfmdlskeleton"
    bl_label = "Import Skeleton"
    
    bfmdl_id = StringProperty()
    
    def execute(self, context):
        if context.scene.bfmdl_source_armature not in context.scene.objects: self.report({'ERROR'}, "Source object's armature not specified."); return {'CANCELLED'}
        SaveBFMDL_Skeleton(context.scene.bfres.data.models[self.bfmdl_id], self.bfmdl_id, context.scene.objects[context.scene.bfmdl_source_armature], operator=self)
        return {'FINISHED'}
class LoadBFMDLtoScene(bpy.types.Operator):
    """Loads the BFMDL model into the target blender object"""
    bl_idname = "scene.exportbfmdl"
    bl_label = "Load to Target"
    
    bfmdl_id = StringProperty()
    
    
    def execute(self, context):
        if context.scene.bfmdl_target_model not in context.scene.objects:
            context.scene.bfmdl_target_model = self.bfmdl_id
            mesh = bpy.data.meshes.new(self.bfmdl_id)
            obj = bpy.data.objects.new(self.bfmdl_id, mesh)
            context.scene.objects.link(obj)
        else: obj = context.scene.objects[context.scene.bfmdl_target_model]
        LoadBFMDL_Mesh(context.scene.bfres.data.models[self.bfmdl_id], self.bfmdl_id, arm = context.scene.objects.get(self.bfmdl_id + "_armature"), target_obj = obj, operator=self)
        return {'FINISHED'}
class SaveBFMDLfromScene(bpy.types.Operator):
    """Writes into the BFMDL model data from the source blender object"""
    bl_idname = "scene.importbfmdl"
    bl_label = "Import from Source"
    
    bfmdl_id = StringProperty()
    
    
    def execute(self, context):
        if context.scene.bfmdl_source_model not in context.scene.objects: self.report({'ERROR'}, "Source object not specified."); return {'CANCELLED'}
        SaveBFMDL_Mesh(context.scene.bfres.data.models[self.bfmdl_id], self.bfmdl_id, source_obj = context.scene.objects[context.scene.bfmdl_source_model], operator=self)
        return {'FINISHED'}

class ExportBFTEXMipmapToImage(bpy.types.Operator):
    """Exports the BFTEX mipmap into the target blender image"""
    bl_idname = "scene.exportbftex"
    bl_label = "Export to Target"
    
    bftex_id = StringProperty()
    mip_id = IntProperty()
    
    @classmethod
    def poll(cls, context):
        return context.scene.bftex_target_image in bpy.data.images
    
    def execute(self, context):
        print("Export texture %s mip %i to blender image %s" % (self.bftex_id, self.mip_id, str(bpy.data.images[context.scene.bftex_target_image])))
        LoadBFTEX(context.scene.bfres.data.textures[self.bftex_id], self.bftex_id, self.mip_id, img=bpy.data.images[context.scene.bftex_target_image], operator=self)
        return {'FINISHED'}
class ImportBFTEXMipmapFromImage(bpy.types.Operator):
    """Imports the source blender image into the BFTEX"""
    bl_idname = "scene.importbftex"
    bl_label = "Import from Source"
    
    bftex_id = StringProperty()
    mip_id = IntProperty()
    
    @classmethod
    def poll(cls, context):
        return context.scene.bftex_source_image in bpy.data.images
    
    def execute(self, context):
        ftex = context.scene.bfres.data.textures[self.bftex_id]
        print("Import texture %s mip %i from blender image %s" % (self.bftex_id, self.mip_id, str(bpy.data.images[context.scene.bftex_source_image])))
        SaveBFTEX(ftex, self.bftex_id, self.mip_id, bpy.data.images[context.scene.bftex_source_image], operator=self)
        return {'FINISHED'}

class OpenCEMUBFRESFINDER(bpy.types.Operator):
    """Opens the CEMU BFRES Finder window"""
    bl_idname = "scene.opencemubfresfinder"
    bl_label = "Find BFRES Files"
    
    def execute(self, context):
        subprocess.call([bpy.context.user_preferences.filepaths.temporary_directory+"CEMU_BFRES_FINDER.exe"])
        return {'FINISHED'}

class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'

class BFRES_Tcp_Gecko_Panel(View3DPanel, bpy.types.Panel):
    bl_label = "TCP Gecko"
    bl_idname = "OBJECT_PT_BFRESTCPGECKO"
    bl_category = "BFRES"
    bl_context = "objectmode"
    def draw(self, context):
        global sock, TCPBFRESLIST, currentDownloadedID
        layout = self.layout
        row = layout.row()
        row.prop(context.scene, "tcp_gecko_IP")
        row = layout.row()
        row.operator("scene.findwiiu")
        row = layout.row()
        if sock is None:
            row.operator("scene.connectwiiu")
            return
        row.operator("scene.disconnectwiiu")
        row = layout.row()
        row.operator("scene.getbfreslist")
        if len(TCPBFRESLIST) > 0:
            row = layout.row()
            layout.row().prop(context.scene, "tcp_gecko_bfres_name_search")
            layout.row().prop(context.scene, "tcp_gecko_bfres_size_search")
        row = layout.row()
        row.label("Found %i BFRES headers." % len(TCPBFRESLIST))
        i = 0
        for TCPBFRES in TCPBFRESLIST:
            show_bfres_data = True
            if context.scene.tcp_gecko_bfres_name_search != "" and context.scene.tcp_gecko_bfres_name_search not in TCPBFRES[2]:None
            elif context.scene.tcp_gecko_bfres_size_search[0]*1024 >= TCPBFRES[1]:None
            elif context.scene.tcp_gecko_bfres_size_search[1]*1024 <= TCPBFRES[1]:None
            elif show_bfres_data:
                layout.row().label("Name: " + TCPBFRES[2])
                layout.row().label("Size: %skb" % str(round(TCPBFRES[1]/1024.0, 2)))
                row = layout.row()
                row.operator("scene.downloadbfres").id = i
                layout.row()
                layout.row()
            i+=1
            
class BFRES_CEMU_Panel(View3DPanel, bpy.types.Panel):
    bl_label = "CEMU"
    bl_idname = "OBJECT_PT_BFRESCEMU"
    bl_category = "BFRES"
    bl_context = "objectmode"
    def draw(self, context):
        layout = self.layout
        layout.row().operator("scene.opencemubfresfinder")

class BFRESMainToolPanel(View3DPanel, bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_idname = "OBJECT_PT_BFRES"
    bl_category = "BFRES"
    bl_context = "objectmode"
    bl_label = "Main BFRES Tools"
    

    def draw(self, context):
        layout = self.layout

        obj = context.object
        
        row = layout.row()
        row.operator("scene.import_bfres")
        layout.row().operator("scene.restorebfres")
        layout.row().operator("scene.savebfrestofile")
        layout.row().operator("scene.savebfrestofilepatch")
        if len(context.scene.objects) != 0:
            row = layout.row()
            row.label("This scene must be empty to load bfres files.", icon='INFO')
        layout.row().operator("scene.loadbfres")
        
class BFMDLManager(View3DPanel, bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Models"
    bl_idname = "OBJECT_PT_BFMDL"
    bl_category = "BFRES"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop_search(context.scene, "bfmdl_target_armature", context.scene, "objects")
        row.operator("scene.bfmdlaototargetarmature", icon='GO_LEFT')
        row = layout.row()
        row.prop_search(context.scene, "bfmdl_target_model", context.scene, "objects")
        row.operator("scene.bfmdlaototarget", icon='GO_LEFT')
        row = layout.row()
        row.prop_search(context.scene, "bfmdl_source_armature", context.scene, "objects")
        row.operator("scene.bfmdlaotosourcearmature", icon='GO_LEFT')
        row = layout.row()
        row.prop_search(context.scene, "bfmdl_source_model", context.scene, "objects")
        row.operator("scene.bfmdlaotosource", icon='GO_LEFT')
        if context.scene.bfres.data is None:
            layout.row().label("No BFRES loaded.", icon='INFO')
            return
        layout.row().label("There are %i models in this BFRES." % len(context.scene.bfres.data.models))
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        for mname in context.scene.bfres.data.models:
            mdl = context.scene.bfres.data.models[mname]
            layout.row().operator("scene.showhidebfmdltools", icon='TRIA_DOWN' if mdl.display_info else 'TRIA_RIGHT', text=mname, emboss=False).bfmdl_id = mname
            if not mdl.display_info:continue
            layout.row().label("Number of polygons: " + str(mdl.get_polygon_count()))
            row = layout.row()
            row.label("Current lod: "+str(mdl.lod))
            row.operator("scene.bfmdlloddown", icon='ZOOMOUT').bfmdl_id = mname
            row.operator("scene.bfmdllodup", icon='ZOOMIN').bfmdl_id = mname
            esklop = layout.row().operator("scene.exportbfmdlskeleton")
            esklop.bfmdl_id = mname
            isklop = layout.row().operator("scene.importbfmdlskeleton")
            isklop.bfmdl_id = mname
            emdlop = layout.row().operator("scene.exportbfmdl")
            emdlop.bfmdl_id = mname
            imdlop = layout.row().operator("scene.importbfmdl")
            imdlop.bfmdl_id = mname
            for pname in mdl.polygons:
                layout.row()
                layout.row()
                layout.row().label("Polygon: "+pname)
                layout.row().label("Lod: "+str(mdl.polygons[pname].LoD_model_count()))
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
           
class BFTEXManager(View3DPanel, bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Textures"
    bl_idname = "OBJECT_PT_BFTEX"
    bl_category = "BFRES"

    def draw(self, context):
        layout = self.layout
        layout.row().prop_search(context.scene, "bftex_target_image", bpy.data, "images")
        layout.row().prop_search(context.scene, "bftex_source_image", bpy.data, "images")
        if context.scene.bfres.data is None:
            layout.row().label("No BFRES loaded.", icon='INFO')
            return
        layout.row().label("There are %i textures in this BFRES." % len(context.scene.bfres.data.textures))
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        layout.row()
        for tname in context.scene.bfres.data.textures:
            tex = context.scene.bfres.data.textures[tname]
            layout.row().operator("scene.showhidebftextools", icon='TRIA_DOWN' if tex.display_info else 'TRIA_RIGHT', text=tname, emboss=False).bftex_id = tname
            if not tex.display_info:continue
            layout.row().label("Base Dimensions: %ix%i" % (tex.width(), tex.height()))
            layout.row().label("Format: %s" % tex.format_string())
            layout.row().label("Mipmaps: %i" % tex.num_bitmaps_again())
            impaop = layout.row().operator("scene.importbftex", text="Import from Source")
            impaop.bftex_id = tname
            impaop.mip_id = -1
            for i in range(tex.num_bitmaps_again()):
                layout.row().label("Mipmap size: %ix%i" % (max(tex.width()>>i, 1), max(tex.height()>>i, 1)))
                row = layout.row()
                expop = row.operator("scene.exportbftex")
                expop.bftex_id = tname
                expop.mip_id = i
                impop = row.operator("scene.importbftex")
                impop.bftex_id = tname
                impop.mip_id = i
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()
            layout.row()



def register():
    bpy.types.Scene.bfres = BFRESslot
    bpy.types.Scene.tcp_gecko_IP = StringProperty(name="IP Address")
    bpy.types.Scene.tcp_gecko_bfres_name_search = StringProperty(name="Search by name")
    bpy.types.Scene.tcp_gecko_bfres_size_search = FloatVectorProperty(name="Search by size", size = 2, default = (0, 100000000))
    bpy.types.Scene.bftex_target_image = StringProperty(name="Target Image")
    bpy.types.Scene.bftex_source_image = StringProperty(name="Source Image")
    bpy.types.Scene.bfmdl_target_model = StringProperty(name="Target Model")
    bpy.types.Scene.bfmdl_source_model = StringProperty(name="Source Model")
    bpy.types.Scene.bfmdl_target_armature = StringProperty(name="Target Armature")
    bpy.types.Scene.bfmdl_source_armature = StringProperty(name="Source Armeture")
    bpy.utils.register_class(LoadBFRESToScene)
    bpy.utils.register_class(ImportBFRES)
    bpy.utils.register_class(FindWiiUIP)
    bpy.utils.register_class(ConnectToWiiU)
    bpy.utils.register_class(DisconnectWiiU)
    bpy.utils.register_class(GetBFRESList)
    bpy.utils.register_class(DownloadBFRES)
    bpy.utils.register_class(RestoreBFRES)
    bpy.utils.register_class(SaveBFRESToFilePatches)
    bpy.utils.register_class(SaveBFRESToFile)
    bpy.utils.register_class(ShowHideBFTEXTools)
    bpy.utils.register_class(ShowHideBFMDLTools)
    bpy.utils.register_class(ActiveObjectToTarget)
    bpy.utils.register_class(ActiveObjectToSource)
    bpy.utils.register_class(ActiveObjectToTargetArmature)
    bpy.utils.register_class(ActiveObjectToSourceArmature)
    bpy.utils.register_class(DecreaseLod)
    bpy.utils.register_class(IncreaseLod)
    bpy.utils.register_class(SaveBFMDLSkeletonfromScene)
    bpy.utils.register_class(LoadBFMDLSkeletontoScene)
    bpy.utils.register_class(LoadBFMDLtoScene)
    bpy.utils.register_class(SaveBFMDLfromScene)
    bpy.utils.register_class(ExportBFTEXMipmapToImage)
    bpy.utils.register_class(ImportBFTEXMipmapFromImage)
    bpy.utils.register_class(OpenCEMUBFRESFINDER)
    bpy.utils.register_class(BFRES_Tcp_Gecko_Panel)
    bpy.utils.register_class(BFRES_CEMU_Panel)
    bpy.utils.register_class(BFRESMainToolPanel)
    bpy.utils.register_class(BFMDLManager)
    bpy.utils.register_class(BFTEXManager)


def unregister():
    bpy.utils.unregister_class(LoadBFRESToScene)
    bpy.utils.unregister_class(ImportBFRES)
    bpy.utils.unregister_class(FindWiiUIP)
    bpy.utils.unregister_class(ConnectToWiiU)
    bpy.utils.unregister_class(DisconnectWiiU)
    bpy.utils.unregister_class(GetBFRESList)
    bpy.utils.unregister_class(DownloadBFRES)
    bpy.utils.unregister_class(RestoreBFRES)
    bpy.utils.unregister_class(SaveBFRESToFilePatches)
    bpy.utils.unregister_class(SaveBFRESToFile)
    bpy.utils.unregister_class(ShowHideBFTEXTools)
    bpy.utils.unregister_class(ShowHideBFMDLTools)
    bpy.utils.unregister_class(ActiveObjectToTarget)
    bpy.utils.unregister_class(ActiveObjectToSource)
    bpy.utils.unregister_class(ActiveObjectToTargetArmature)
    bpy.utils.unregister_class(ActiveObjectToSourceArmature)
    bpy.utils.unregister_class(DecreaseLod)
    bpy.utils.unregister_class(IncreaseLod)
    bpy.utils.unregister_class(SaveBFMDLSkeletonfromScene)
    bpy.utils.unregister_class(LoadBFMDLSkeletontoScene)
    bpy.utils.unregister_class(LoadBFMDLtoScene)
    bpy.utils.unregister_class(SaveBFMDLfromScene)
    bpy.utils.unregister_class(ExportBFTEXMipmapToImage)
    bpy.utils.unregister_class(ImportBFTEXMipmapFromImage)
    bpy.utils.unregister_class(OpenCEMUBFRESFINDER)
    bpy.utils.unregister_class(BFRES_Tcp_Gecko_Panel)
    bpy.utils.unregister_class(BFRES_CEMU_Panel)
    bpy.utils.unregister_class(BFRESMainToolPanel)
    bpy.utils.unregister_class(BFMDLManager)
    bpy.utils.unregister_class(BFTEXManager)


if __name__ == "__main__":
    register()
