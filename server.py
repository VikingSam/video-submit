#!/usr/bin/env python3
"""Video Submit Backend — receives uploads from the portal and routes them correctly."""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os, shutil, requests, datetime

app = Flask(__name__)
CORS(app)

VIDEO_DIR = os.path.expanduser("~/clawd/video-inbox/videos")
TRANSCRIPT_DIR = os.path.expanduser("~/clawd/video-inbox/transcripts")
THUMBNAIL_DIR = os.path.expanduser("~/clawd/video-inbox/thumbnails")

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

TELEGRAM_BOT = "8392871149:AAHZazO8sJsExVppa8gdw_FM422HA35747E"
TELEGRAM_CHAT = "8323924187"

def telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg}, timeout=10)
    except:
        pass

@app.route("/upload", methods=["POST"])
def upload():
    try:
        video_type = request.form.get("type", "full")
        notes = request.form.get("notes", "")
        thumb169 = request.form.get("thumb169", "")
        thumb916 = request.form.get("thumb916", "")

        saved = []

        # Save video file(s)
        for key, label in [("video", "Full"), ("short", "Short")]:
            if key in request.files:
                f = request.files[key]
                if f.filename:
                    dest = os.path.join(VIDEO_DIR, f.filename)
                    f.save(dest)
                    saved.append(f"{label} Video: {f.filename}")

        # Save transcript file
        transcript_name = None
        if "transcript" in request.files:
            f = request.files["transcript"]
            if f.filename:
                dest = os.path.join(TRANSCRIPT_DIR, f.filename)
                f.save(dest)
                transcript_name = f.filename
                saved.append(f"Transcript: {f.filename}")

        # Save thumbnails
        for key, label in [("thumb169", "16x9"), ("thumb916", "9x16")]:
            if key in request.files:
                f = request.files[key]
                if f.filename:
                    name, ext = os.path.splitext(f.filename)
                    dest = os.path.join(THUMBNAIL_DIR, f"{name}_{label}{ext}")
                    f.save(dest)
                    saved.append(f"Thumbnail {label}: {f.filename}")

        if not saved:
            return jsonify({"ok": False, "error": "No files received"}), 400

        # SCP files to Bubba's workspace on Botbeast
        import subprocess
        BOTBEAST = "botbeast@100.69.80.112"
        BUBBA_INBOX = "/Users/botbeast/bubba/video-inbox"
        files_to_scp = []
        for key in ['video', 'short']:
            if key in request.files and request.files[key].filename:
                files_to_scp.append((os.path.join(VIDEO_DIR, request.files[key].filename), 'videos'))
        if 'transcript' in request.files and request.files['transcript'].filename:
            files_to_scp.append((os.path.join(TRANSCRIPT_DIR, request.files['transcript'].filename), 'transcripts'))
        for filepath, subdir in files_to_scp:
            if filepath and os.path.exists(filepath):
                subprocess.run(['scp', '-o', 'StrictHostKeyChecking=no', filepath, f"{BOTBEAST}:{BUBBA_INBOX}/{subdir}/"], capture_output=True)
        for key, label in [('thumb169','thumbnails'), ('thumb916','thumbnails')]:
            if key in request.files and request.files[key].filename:
                name, ext = os.path.splitext(request.files[key].filename)
                local = os.path.join(THUMBNAIL_DIR, f"{name}_{label}{ext}")
                if os.path.exists(local):
                    subprocess.run(['scp', '-o', 'StrictHostKeyChecking=no', local, f"{BOTBEAST}:{BUBBA_INBOX}/thumbnails/"], capture_output=True)

        # Notify Blade via Telegram
        parent_id = request.form.get("parent_id", "")
        parent_title = request.form.get("parent_title", "")
        type_label = "Full Video" if video_type == "full" else "Short" if video_type == "short" else "Full + Short"
        parent_info = f"\nParent Full Video: {parent_title}" if parent_title else ""
        thumb_info = ""
        if thumb169: thumb_info += f"\n16:9 link: {thumb169}"
        if thumb916: thumb_info += f"\n9:16 link: {thumb916}"
        notes_info = f"\nNotes: {notes}" if notes else ""

        msg = f"🎬 New video drop from Sam!\n\nType: {type_label}\n" + "\n".join(saved) + parent_info + thumb_info + notes_info + f"\n\nFiles → Bubba's inbox on Botbeast"
        telegram(msg)

        return jsonify({"ok": True, "saved": saved})

    except Exception as e:
        telegram(f"⚠️ Video upload error: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/videos")
def get_videos():
    """Return list of full videos from Airtable Video Registry for the dropdown."""
    try:
        MATON_KEY = "4fYrutTuer3xhxhdyvNHieAkYoDq-1GUpIrnwBqyHqyU6Xl_YBI1Dl0Xe17j-JUEWAd0_DV6yjFQq7XSbpSH-YdgABPWNVfPeo4"
        resp = requests.get(
            "https://gateway.maton.ai/airtable/v0/apphRVhGXOrjVMRNn/Video%20Registry",
            headers={"Authorization": f"Bearer {MATON_KEY}"},
            params={"sort[0][field]": "Date Posted", "sort[0][direction]": "desc", "maxRecords": 50},
            timeout=10
        )
        data = resp.json()
        videos = []
        for rec in data.get("records", []):
            f = rec.get("fields", {})
            videos.append({
                "id": rec["id"],
                "title": f.get("Title", "Untitled"),
                "date": f.get("Date Posted", "")
            })
        return jsonify({"ok": True, "videos": videos})
    except Exception as e:
        return jsonify({"ok": False, "videos": [], "error": str(e)})

# Also handle parent video info in upload
# (server already logs it via the saved list — Telegram message will include it)

@app.route("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8893, debug=False)
