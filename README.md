diff --git a/README.md b/README.md
index 65835fad160b10fa832c2d06d9e202f8eed3e064..649418325b0832b51f0a02cd21c0180b52842d8d 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,21 @@
-# Web-kep
-This bokep web will changes you
+# Valtrix Leng
+
+Valtrix Leng adalah web-based Lua obfuscator dengan UI futuristik yang nyaman dipakai untuk workflow proteksi script.
+
+## Fitur
+- Rename variabel lokal & nama function.
+- Encoding string literal via runtime decoder.
+- Junk code injection.
+- Loader wrapper berbasis base64.
+- REST API endpoint: `POST /api/obfuscate`.
+
+## Jalankan
+```bash
+pip install -r requirements.txt
+python app.py
+```
+
+Lalu buka `http://127.0.0.1:5000`.
+
+## Catatan
+Tool ini ditujukan untuk code protection dan distribusi release. Tidak ada sistem yang 100% anti-deobfuscation.
