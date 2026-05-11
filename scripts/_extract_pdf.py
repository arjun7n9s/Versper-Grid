from pypdf import PdfReader
import sys
r = PdfReader(sys.argv[1])
print(f"PAGES: {len(r.pages)}")
for i, p in enumerate(r.pages):
    print(f"\n===== PAGE {i+1} =====\n")
    try:
        print(p.extract_text())
    except Exception as e:
        print(f"[error: {e}]")
