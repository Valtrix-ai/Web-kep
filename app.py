from flask import Flask, render_template

app = Flask(__name__)

# Route untuk halaman utama
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Berjalan di port 8080 agar kompatibel dengan standar cloud/Railway
    app.run(host='0.0.0.0', port=8080, debug=True)
