import sys, os
import fitz  # PyMuPDF
src = sys.argv[1]
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
doc = fitz.open(src)
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=140)
    pix.save(os.path.join(out, f"page_{i+1:02d}.png"))
print(f"Rendered {len(doc)} pages to {out}")
