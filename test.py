import requests

url = "http://9.235.120.52/transcript"
file_path = "aaaa.wav"  # ton fichier audio local

with open(file_path, "rb") as f:
    files = {"file": (file_path, f, "audio/wav")}
    response = requests.post(url, files=files)

print("Status code:", response.status_code)
print("Response:")
print(response.text)
