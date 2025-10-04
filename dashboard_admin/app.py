from flask import Flask, jsonify, request
from flask_cors import CORS
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient, ContentSettings
import json
import re
import requests

app = Flask(__name__)
CORS(app)

# --- Configurations Azure ---
STORAGE_ACCOUNT = "mystorageacct2025xyz123"
ACCOUNT_KEY = "<    YOUR_ACCOUNT_KEY    >"
QUEUE_NAME = "audioworkflowqueue"#my queue
CONTAINER_NAME = "datasets"
SAS_TOKEN_BLOB = "<    YOUR_SAS_TOKEN_BLOB    >"

# --- Clients Azure ---
queue_service = QueueServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.queue.core.windows.net",
    credential=ACCOUNT_KEY
)
queue_client = queue_service.get_queue_client(QUEUE_NAME)

blob_service = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.blob.core.windows.net",
    credential=SAS_TOKEN_BLOB
)
container_client = blob_service.get_container_client(CONTAINER_NAME)

# --- Helpers ---
def get_audio_url_from_id(file_id):
    return f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/audio_{file_id}.wav?{SAS_TOKEN_BLOB}"

def get_response_url_from_id(file_id):
    return f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/response_{file_id}.json?{SAS_TOKEN_BLOB}"

# --- Routes ---
@app.route("/api/files-debug", methods=["GET"])
def get_messages_debug():
    """Affiche tous les messages de la queue sans les supprimer"""
    try:
        messages = queue_client.receive_messages(messages_per_page=10, visibility_timeout=0)
        debug_list = []

        for msg in messages:
            debug_list.append({
                "message_id": msg.id,
                "pop_receipt": msg.pop_receipt,
                "content": msg.content
            })

        return jsonify({"status": "debug", "messages_found": len(debug_list), "messages": debug_list})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

import base64

@app.route("/api/files", methods=["GET"])
def get_messages():
    """Récupère et parse les messages sans les supprimer"""
    try:
        messages = queue_client.receive_messages(messages_per_page=10, visibility_timeout=1)
        result = []

        for msg in messages:
            try:
                # Décoder Base64 si nécessaire
                try:
                    decoded_content = base64.b64decode(msg.content).decode("utf-8")
                    event = json.loads(decoded_content)
                except Exception:
                    # Fallback : essayer de parser directement
                    event = json.loads(msg.content)

                blob_url = event.get("data", {}).get("url") or event.get("subject") or ""
                audio_match = re.search(r"audio_(\d+)\.wav", blob_url)
                response_match = re.search(r"response_(\d+)\.json", blob_url)

                if audio_match:
                    file_id = audio_match.group(1)
                elif response_match:
                    file_id = response_match.group(1)
                else:
                    file_id = "unknown"

                audio_url = get_audio_url_from_id(file_id)
                response_url = get_response_url_from_id(file_id)

                transcription = {}
                try:
                    r = requests.get(response_url, timeout=5)
                    if r.ok:
                        transcription = r.json()
                except Exception as req_e:
                    print(f"[DEBUG] Failed fetching transcription: {req_e}")

                result.append({
                    "id": file_id,
                    "audio_url": audio_url,
                    "response_url": response_url,
                    "transcription": transcription,
                    "message_id": msg.id,
                    "pop_receipt": msg.pop_receipt,
                    "timestamp": event.get("eventTime", "")
                })

            except Exception as e:
                print(f"[ERROR] Error processing message {msg.id}: {e}")
                continue

        return jsonify({"status": "success", "count": len(result), "files": result})

    except Exception as e:
        print(f"[ERROR] Error in get_messages: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/files/<file_id>/validate", methods=["POST"])
def validate_file(file_id):
    """Valide un message et supprime de la queue après sauvegarde"""
    try:
        data = request.json
        message_id = data.get("message_id")
        pop_receipt = data.get("pop_receipt")
        corrected_text = data.get("corrected_text")
        status = data.get("status", "approved")

        corrected_data = {
            "file_id": file_id,
            "corrected_text": corrected_text,
            "status": status,
            "validated_at": data.get("validated_at")
        }

        corrected_blob_name = f"corrected_{file_id}.json"
        blob_client = container_client.get_blob_client(corrected_blob_name)
        blob_client.upload_blob(
            json.dumps(corrected_data, indent=2),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json")
        )

        # Supprimer le message seulement après validation
        if message_id and pop_receipt:
            queue_client.delete_message(message_id, pop_receipt)

        return jsonify({"status": "success", "corrected_blob": corrected_blob_name})

    except Exception as e:
        print(f"[ERROR] Validation error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

# --- Main ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
