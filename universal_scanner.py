import cv2
from pyzbar.pyzbar import decode
import urllib.parse
import base64
import struct
import os
import tkinter as tk
from tkinter import filedialog


# --- GOOGLE PROTOBUF PARSING LOGIC (UNCHANGED) ---
def read_varint(data, index):
    value = 0
    shift = 0
    while True:
        if index >= len(data):
            raise IndexError("Unexpected end of data")
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return value, index


def decode_google_payload(data_str):
    try:
        padding = '=' * (-len(data_str) % 4)
        buffer = base64.urlsafe_b64decode(data_str + padding)
    except Exception as e:
        print(f"Error decoding Base64: {e}")
        return []

    index = 0
    secrets = []
    while index < len(buffer):
        try:
            tag, index = read_varint(buffer, index)
        except IndexError:
            break
        wire_type = tag & 0x07
        field_number = tag >> 3

        if wire_type == 2:
            length, index = read_varint(buffer, index)
            payload = buffer[index: index + length]
            index += length
            if field_number == 1:
                account = parse_otp_parameters(payload)
                if account: secrets.append(account)
    return secrets


def parse_otp_parameters(payload):
    index = 0
    secret_bytes = None
    name = "Unknown"
    issuer = "Unknown"
    while index < len(payload):
        try:
            tag, index = read_varint(payload, index)
        except IndexError:
            break
        wire_type = tag & 0x07
        field_number = tag >> 3

        if wire_type == 2:
            length, index = read_varint(payload, index)
            value = payload[index: index + length]
            index += length
            if field_number == 1:
                secret_bytes = value
            elif field_number == 2:
                name = value.decode('utf-8', errors='ignore')
            elif field_number == 3:
                issuer = value.decode('utf-8', errors='ignore')
        elif wire_type == 0:
            _, index = read_varint(payload, index)

    if secret_bytes:
        secret_b32 = base64.b32encode(secret_bytes).decode('utf-8').replace('=', '')
        return {"name": name, "issuer": issuer, "secret": secret_b32}
    return None


# --- SCANNING LOGIC (UPDATED TO RETURN DATA) ---

def process_image_data(image):
    """
    Takes an OpenCV image, finds QRs, and returns a list of account dicts.
    """
    decoded_objects = decode(image)
    found_accounts = []

    if not decoded_objects:
        print("No QR code found in image.")
        return []

    for obj in decoded_objects:
        url = obj.data.decode('utf-8')

        # CASE 1: Google Migration QR
        if "otpauth-migration://" in url:
            print("\n[DETECTED] Google Migration QR!")
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            if 'data' in qs:
                accounts = decode_google_payload(qs['data'][0])
                found_accounts.extend(accounts)

        # CASE 2: Standard QR
        elif "otpauth://" in url:
            print("\n[DETECTED] Standard TOTP QR!")
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            secret = params.get('secret', [None])[0]
            label = parsed.path.strip('/')

            # Try to split label into Issuer:Name
            if ":" in label:
                issuer, name = label.split(":", 1)
            else:
                issuer = "Standard"
                name = label

            if secret:
                found_accounts.append({
                    "name": name,
                    "issuer": issuer,
                    "secret": secret
                })

    return found_accounts


def select_file_and_scan():
    """Opens file dialog, scans image, and returns list of accounts found."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select QR Code Screenshot",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")]
    )
    if file_path:
        print(f"\nProcessing file: {file_path}")
        img = cv2.imread(file_path)
        if img is None:
            print("Error: Could not read image file.")
            return []

        results = process_image_data(img)
        return results
    return []


def run_webcam_scan():
    """Runs webcam, returns first found account list."""
    print("\n--- WEBCAM MODE ---")
    print("Press 'q' to quit scanning.")
    cap = cv2.VideoCapture(0)
    found_accounts = []

    while True:
        ret, frame = cap.read()
        if not ret: break

        decoded_objects = decode(frame)
        if decoded_objects:
            # If we found something, process it and return immediately
            found_accounts = process_image_data(frame)
            if found_accounts:
                cap.release()
                cv2.destroyAllWindows()
                return found_accounts

        cv2.imshow('Webcam Scanner', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return []