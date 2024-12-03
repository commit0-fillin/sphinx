"""PNG image manipulation helpers."""
from __future__ import annotations
import binascii
import struct
LEN_IEND = 12
LEN_DEPTH = 22
DEPTH_CHUNK_LEN = struct.pack('!i', 10)
DEPTH_CHUNK_START = b'tEXtDepth\x00'
IEND_CHUNK = b'\x00\x00\x00\x00IEND\xaeB`\x82'

def read_png_depth(filename: str) -> int | None:
    """Read the special tEXt chunk indicating the depth from a PNG file."""
    with open(filename, 'rb') as f:
        # Skip the PNG signature (8 bytes) and IHDR chunk (25 bytes)
        f.seek(33)
        
        while True:
            chunk_len = struct.unpack('!I', f.read(4))[0]
            chunk_type = f.read(4)
            
            if chunk_type == b'tEXt':
                chunk_data = f.read(chunk_len)
                if chunk_data.startswith(DEPTH_CHUNK_START):
                    depth_str = chunk_data[len(DEPTH_CHUNK_START):].decode('ascii')
                    return int(depth_str)
            elif chunk_type == b'IEND':
                break
            else:
                f.seek(chunk_len + 4, 1)  # Skip chunk data and CRC
        
    return None

def write_png_depth(filename: str, depth: int) -> None:
    """Write the special tEXt chunk indicating the depth to a PNG file.

    The chunk is placed immediately before the special IEND chunk.
    """
    with open(filename, 'rb+') as f:
        f.seek(-LEN_IEND, 2)  # Go to the start of IEND chunk
        
        # Read the entire file except the IEND chunk
        png_data = f.read(f.tell())
        
        # Create the depth chunk
        depth_data = DEPTH_CHUNK_START + str(depth).encode('ascii')
        depth_chunk = (
            DEPTH_CHUNK_LEN +
            b'tEXt' +
            depth_data +
            struct.pack('!I', binascii.crc32(b'tEXt' + depth_data))
        )
        
        # Write the file with the new depth chunk
        f.seek(0)
        f.write(png_data + depth_chunk + IEND_CHUNK)
