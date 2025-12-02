from flask import Flask, request, jsonify, send_file, render_template
import re
import os
import subprocess
import zipfile
import io
from pathlib import Path
import time

app = Flask(__name__)

MAX_TOTAL_REQUEST_SIZE = int(os.getenv('MAX_TOTAL_REQUEST_SIZE', 500 * 1024 * 1024))
MAX_SINGLE_FILE_SIZE = int(os.getenv('MAX_SINGLE_FILE_SIZE', 100 * 1024 * 1024))
MAX_FILES_COUNT = int(os.getenv('MAX_FILES_COUNT', 100))
CONVERSION_TIMEOUT = int(os.getenv('CONVERSION_TIMEOUT', 30))

app.config['MAX_CONTENT_LENGTH'] = MAX_TOTAL_REQUEST_SIZE

UPLOAD_FOLDER = '/app/uploads'
CONVERTED_FOLDER = '/app/converted'
ALLOWED_EXTENSIONS = {'psd'}

Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(CONVERTED_FOLDER).mkdir(exist_ok=True)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def custom_secure_filename(filename):
    return re.sub(r'[^\wа-яА-ЯёЁ\.-]', '_', filename)

def validate_files(files):
    errors = []
    
    if len(files) > MAX_FILES_COUNT:
        errors.append(f"Слишком много файлов. Максимум: {MAX_FILES_COUNT}")
        return errors
    
    total_size = 0
    
    
    for file in files:
        if file and allowed_file(file.filename):
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > MAX_SINGLE_FILE_SIZE:
                errors.append(f"Файл {file.filename} слишком большой ({file_size // (1024*1024)}MB). Максимум: {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB")
            
            total_size += file_size
        elif file:
            errors.append(f"Файл {file.filename} не в формате PSD")
    
    if total_size > MAX_TOTAL_REQUEST_SIZE:
        errors.append(f"Общий размер файлов ({total_size // (1024*1024)}MB) превышает лимит ({MAX_TOTAL_REQUEST_SIZE // (1024*1024)}MB)")
    
    return errors

def cleanup_old_files():
    try:
        current_time = time.time()
        for folder in [UPLOAD_FOLDER, CONVERTED_FOLDER]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):

                    if current_time - os.path.getctime(file_path) > 3600:
                        os.remove(file_path)
                        print(f"Cleaned up old file: {filename}")
    except Exception as e:
        print(f"Cleanup error: {e}")

def convert_psd_to_png(psd_path, output_path):
    try:
        cmd = ['convert', f'{psd_path}[0]', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERSION_TIMEOUT)
        
        if result.returncode != 0:
            print(f"Error converting {psd_path}: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"Timeout converting {psd_path}")
        return False
    except Exception as e:
        print(f"Exception converting {psd_path}: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html', 
                         max_files=MAX_FILES_COUNT,
                         max_single_size=MAX_SINGLE_FILE_SIZE // (1024*1024),
                         max_total_size=MAX_TOTAL_REQUEST_SIZE // (1024*1024))

@app.route('/convert', methods=['POST'])
def convert_files():
    cleanup_old_files()
    
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({"error": "No selected files"}), 400

    validation_errors = validate_files(files)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400

    converted_files = []
    failed_files = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = custom_secure_filename(file.filename)
            base_name = Path(filename).stem
            
            psd_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(psd_path)
            
            png_filename = f"{base_name}.png"
            png_path = os.path.join(CONVERTED_FOLDER, png_filename)
            
            if convert_psd_to_png(psd_path, png_path):
                converted_files.append(png_filename)
            else:
                failed_files.append(filename)
            
            try:
                os.remove(psd_path)
            except Exception as e:
                print(f"Error removing PSD file {psd_path}: {e}")

    if converted_files:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for png_file in converted_files:
                png_path = os.path.join(CONVERTED_FOLDER, png_file)
                if os.path.exists(png_path):
                    zip_file.write(png_path, png_file)
        
        zip_buffer.seek(0)
        
        for png_file in converted_files:
            try:
                png_path = os.path.join(CONVERTED_FOLDER, png_file)
                if os.path.exists(png_path):
                    os.remove(png_path)
            except Exception as e:
                print(f"Error removing PNG file {png_file}: {e}")

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'converted_{len(converted_files)}_files.zip',
            mimetype='application/zip'
        )
    else:
        return jsonify({
            "error": "No files were successfully converted",
            "failed_files": failed_files
        }), 500

@app.route('/api/convert', methods=['POST'])
def api_convert():
    return convert_files()

@app.route('/config')
def show_config():
    return jsonify({
        "max_total_request_size_mb": MAX_TOTAL_REQUEST_SIZE // (1024*1024),
        "max_single_file_size_mb": MAX_SINGLE_FILE_SIZE // (1024*1024),
        "max_files_count": MAX_FILES_COUNT,
        "conversion_timeout_seconds": CONVERSION_TIMEOUT
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print(f"Starting PSD Converter with configuration:")
    print(f"  Max total request size: {MAX_TOTAL_REQUEST_SIZE // (1024*1024)}MB")
    print(f"  Max single file size: {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB")
    print(f"  Max files count: {MAX_FILES_COUNT}")
    print(f"  Conversion timeout: {CONVERSION_TIMEOUT}s")
    
    app.run(host='0.0.0.0', port=5000, debug=False)