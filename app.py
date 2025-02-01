import requests
import time
from datetime import datetime, timedelta
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploaded_reels'

# Instagram API Credentials
ACCESS_TOKEN = "EAAHypUNvGAYBOZCQZBzI92imnueLb7Nk3Q0VUZBx3xAJWl5OX6EPnEoKCWoekK5Fw3gqYlZBkira8eZCQy6vTcgLgAC8t1kt56A723ZCZActGk3xpReL9lMnScdgZAnBr2IR6ZBvVADAGs1qan5Ar8ljcZAxBnBxPJ3Mbck36ZBqeLZCUfjxPDLEnexyjlHtdwZDZD"
INSTAGRAM_ACCOUNT_ID = "17841445678217841"
WORDPRESS_URL = 'https://spmb.co.in/wp-json/wp/v2/media'
WORDPRESS_USERNAME = 'admin'
WORDPRESS_APP_PASSWORD = 'LesW Vzp7 1p5a CRAW 2WTt SDSe'

# Load Reels Data
def load_reels_data():
    if os.path.exists('reels_data.json'):
        with open('reels_data.json', 'r') as file:
            return json.load(file)
    return []

# Save Reels Data
def save_reels_data(data):
    with open('reels_data.json', 'w') as file:
        json.dump(data, file, indent=4)

# Upload Reel to WordPress
def upload_to_wordpress(file_path):
    file_name = secure_filename(file_path)
    headers = {'Content-Disposition': f'attachment; filename={file_name}'}

    with open(file_path, 'rb') as file:
        response = requests.post(
            WORDPRESS_URL,
            headers=headers,
            auth=(WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD),
            files={'file': file}
        )

    if response.status_code == 201:
        return response.json()['source_url']
    else:
        print(f'WordPress Upload Error: {response.text}')
        return None

# Upload Reel to Instagram
def upload_video(video_url, caption):
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    }

    response = requests.post(url, params=params)
    data = response.json()

    if "id" in data:
        print(f"Instagram Upload Successful! Media ID: {data['id']}")
        return data["id"]
    else:
        print(f"Instagram Upload Error: {data}")  # Log the error message for debugging
        return None

# Check Media Status
def check_media_status(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}?fields=status_code&access_token={ACCESS_TOKEN}"

    while True:
        response = requests.get(url)
        data = response.json()

        print(f"Checking media status for Media ID {media_id}: {data}")

        status_code = data.get("status_code")
        if status_code == "FINISHED":
            print(f"Media ID {media_id} is ready for publishing.")
            return True
        elif status_code == "ERROR":
            print(f"Media processing failed for Media ID {media_id}.")
            return False
        elif status_code:
            print(f"Media ID {media_id} is in status: {status_code}")
        else:
            print(f"Unexpected response for Media ID {media_id}: {data}")

        time.sleep(10)



# Publish Reel to Instagram
def publish_video(media_id):
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    params = {
        "creation_id": media_id,
        "access_token": ACCESS_TOKEN,
    }

    response = requests.post(url, params=params)
    data = response.json()

    if "id" in data:
        print(f"Video Published Successfully! Post ID: {data['id']}")
    else:
        print(f"Publishing Error for Media ID {media_id}: {data}")

        if "error" in data:
            error_message = data["error"].get("message", "No message provided")
            error_type = data["error"].get("type", "Unknown type")
            error_code = data["error"].get("code", "Unknown code")

            print(f"Error Type: {error_type}, Error Code: {error_code}, Message: {error_message}")



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/post')
def post_page():
    reels_data = load_reels_data()
    return render_template('post.html', reels=reels_data)

@app.route('/upload_reel', methods=['POST'])
def upload_reel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        wordpress_url = upload_to_wordpress(filepath)
        if wordpress_url:
            reels_data = load_reels_data()
            reels_data.append({'video_url': wordpress_url, 'caption': ''})
            save_reels_data(reels_data)

            return jsonify({'success': 'File uploaded successfully!', 'file_url': wordpress_url})
        else:
            return jsonify({'error': 'Failed to upload to WordPress'})

    return jsonify({'error': 'Unexpected error occurred'})


@app.route('/schedule_reels', methods=['POST'])
def schedule_reels():
    data = request.json
    caption = data.get('caption')
    reels = data.get('reels')

    for reel in reels:
        video_url = reel['video_url']
        schedule_time = datetime.strptime(reel['schedule_time'], '%Y-%m-%dT%H:%M')
        
        time_to_wait = (schedule_time - datetime.now()).total_seconds()
        if time_to_wait > 0:
            print(f"Waiting {time_to_wait} seconds to upload reel: {video_url}")
            time.sleep(time_to_wait)
        
        # Upload Video to Instagram
        media_id = upload_video(video_url, caption)
        
        # Introduce a delay after each upload to prevent API rate issues
        time.sleep(5)  # Wait for 5 seconds before checking media status

        if media_id:
            if check_media_status(media_id):
                publish_video(media_id)
                time.sleep(5)  # Wait 5 seconds before the next upload
            else:
                print(f"Media processing failed for reel: {video_url}")
        else:
            print(f"Failed to upload reel: {video_url}")

    return jsonify({'success': 'Reels scheduled successfully!'})


if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, port=5008)
