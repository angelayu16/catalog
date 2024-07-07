import base64
import collections
import main

from io import BytesIO
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

Image = collections.namedtuple("Image", ["file_type", "image_content"])

@app.route('/upload', methods=['POST'])
def upload_file():
    images = []
    files = request.files.getlist('images')

    for image in files:
        filename = secure_filename(image.filename)
        file_type = filename.rsplit('.', 1)[1].lower()

        image_stream = BytesIO()
        image.save(image_stream)
        image_stream.seek(0)
        image_base64 = base64.b64encode(image_stream.read()).decode('utf-8')

        images.append(Image(file_type=file_type, image_content=image_base64))

    main.process_images(images)

    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
