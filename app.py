from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import yt_dlp

app = Flask(__name__)
# Pengaturan proxy agar aman di Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def get_download_links():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'message': 'Link tidak boleh kosong!'})

    # Konfigurasi alat pencari video
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best', # Cari format terbaik
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Kita kumpulkan data video dan audio
            videos = []
            audios = []
            
            # Filter otomatis format yang tersedia dari website aslinya
            for f in info.get('formats', []):
                # Filter MP4 Video
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    res = f.get('height')
                    if res and res >= 360: # Ambil resolusi 360p ke atas
                        videos.append({
                            'label': f"{res}p MP4",
                            'url': f.get('url')
                        })
                
                # Filter Audio
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    bitrate = f.get('abr', 128)
                    if bitrate:
                        audios.append({
                            'label': f"{int(bitrate)}kbps Audio",
                            'url': f.get('url')
                        })

            # Buang duplikat agar tombol tidak dobel-dobel
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())

            # Urutkan dari kualitas tertinggi ke terendah
            videos.sort(key=lambda x: int(x['label'].replace('p MP4', '')), reverse=True)
            audios.sort(key=lambda x: int(x['label'].replace('kbps Audio', '')), reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Media Berhasil Ditemukan'),
                'thumbnail': info.get('thumbnail', ''),
                'videos': videos[:3], # Tampilkan maksimal 3 tombol terbaik
                'audios': audios[:3]  # Tampilkan maksimal 3 tombol terbaik
            })

    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal mengambil video. Pastikan link benar atau coba lagi nanti.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
