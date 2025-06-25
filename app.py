from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import pyttsx3
from concurrent.futures import ThreadPoolExecutor
from ebooklib import epub
import ebooklib
import fitz  # PyMuPDF

app = Flask(__name__)

# Extract text based on file type
def extract_text_from_file(filepath):
    ext = filepath.rsplit('.', 1)[-1].lower()

    if ext == 'txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    elif ext == 'pdf':
        text = ""
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text()
        return text

    elif ext == 'epub':
        book = epub.read_epub(filepath)
        text = ''
        for doc in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = doc.get_content().decode('utf-8')
            text += content + '\n'
        return text

    return None

# Folders for uploads and audio
UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = os.path.join('static', 'audio')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'epub'}

# pyttsx3 engine config
engine = pyttsx3.init()
engine.setProperty('rate', 180)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['ebook']
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            return redirect(url_for('listen', filename=file.filename))
        else:
            return "Invalid file format. Please upload a .txt, .pdf or .epub file."
    return render_template('upload.html')

def generate_chunk_audio(chunk, filename, chunk_num):
    chunk = chunk.strip()
    if not chunk:
        return None

    audio_filename = f"{filename.rsplit('.', 1)[0]}_part{chunk_num}.wav"
    audio_path = os.path.join(AUDIO_FOLDER, audio_filename)

    if not os.path.exists(audio_path):
        local_engine = pyttsx3.init()
        local_engine.setProperty('rate', 180)
        local_engine.save_to_file(chunk, audio_path)
        local_engine.runAndWait()

    return audio_filename

@app.route('/listen/<filename>')
def listen(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    full_text = extract_text_from_file(filepath)
    
    if not full_text:
        return "Failed to extract text from file."

    # Split into ~1000 character chunks
    chunk_size = 1000
    text_chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

    # Convert chunks to audio
    audio_files = []
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(generate_chunk_audio, chunk, filename, i)
            for i, chunk in enumerate(text_chunks)
        ]
        for future in futures:
            result = future.result()
            if result:
                audio_files.append(result)

    return render_template('listen_chunks.html', filename=filename, audio_files=audio_files)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(AUDIO_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
