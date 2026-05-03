# Valtrix Leng

Valtrix Leng adalah web-based Lua obfuscator dengan UI futuristik yang nyaman dipakai untuk workflow proteksi script.

## Fitur
- Rename variabel lokal & nama function.
- Encoding string literal via runtime decoder.
- Junk code injection.
- Loader wrapper berbasis base64.
- REST API endpoint: `POST /api/obfuscate`.

## Jalankan
```bash
pip install -r requirements.txt
python app.py
```

Lalu buka `http://127.0.0.1:5000`.

## Catatan
+Tool ini ditujukan untuk code protection dan distribusi release. Tidak ada sistem yang 100% anti-deobfuscation.
 
EOF
)