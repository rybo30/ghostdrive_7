from PIL import Image
import struct, io

img = Image.open('ghost.png')
blocks = []
for size, ostype in [(16, b'is32'), (32, b'il32'), (64, b'ichk'), (128, b'ic05'), (256, b'ic07'), (512, b'ic08'), (1024, b'ic10')]:
    buf = io.BytesIO()
    img.resize((size, size), Image.Resampling.LANCZOS).save(buf, format='PNG')
    blocks.append(ostype + struct.pack('>I', len(buf.getvalue()) + 8) + buf.getvalue())

with open('ghost.icns', 'wb') as f:
    f.write(b'icns' + struct.pack('>I', sum(len(b) for b in blocks) + 8) + b''.join(blocks))
print('Successfully generated ghost.icns!')
