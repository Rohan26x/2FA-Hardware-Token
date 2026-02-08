import hmac
import hashlib
import time
import struct
import base64


def get_totp_token(secret_key):
    """
    Generates a 6-digit TOTP token based on a Base32 secret key.
    """
    # 1. TIME CALCULATION
    # Get current time in seconds (Unix timestamp)
    current_time = time.time()

    # 2FA codes usually change every 30 seconds (the "time step")
    # We use integer division (//) to get the number of 30-second intervals since 1970.
    time_counter = int(current_time // 30)

    # 2. PACKING THE TIME
    # Convert the time counter into an 8-byte byte string (big-endian).
    # 'miniboss' of the operation: The HMAC algorithm requires bytes, not integers.
    time_bytes = struct.pack('>Q', time_counter)

    # 3. DECODING THE SECRET
    # The secret provided by services (Google/FB) is Base32 encoded.
    # We must decode it back to raw bytes for the math to work.
    # We add padding '=' just in case the key length isn't perfect.
    secret_bytes = base64.b32decode(secret_key.upper() + '=' * (-len(secret_key) % 8))

    # 4. HMAC-SHA1 HASHING
    # This is the core crypto. We hash the Time Bytes using the Secret Bytes.
    hmac_hash = hmac.new(secret_bytes, time_bytes, hashlib.sha1).digest()

    # 5. DYNAMIC TRUNCATION
    # We need to extract 4 bytes from the hash to make our 6-digit code.
    # The index is determined by the last 4 bits of the hash.
    offset = hmac_hash[-1] & 0x0F

    # Take 4 bytes starting from the offset
    truncated_hash = hmac_hash[offset:offset + 4]

    # Convert those bytes to a standard integer (ignoring the most significant bit)
    code_int = struct.unpack('>I', truncated_hash)[0] & 0x7FFFFFFF

    # 6. FINAL FORMATTING
    # Modulo 1,000,000 to get the last 6 digits.
    token = code_int % 1000000

    # Return as a zero-padded string (e.g., "054321" instead of "54321")
    return "{:06d}".format(token)


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # TEST SECRET
    # This is a random Base32 string (simulating a secret from Google/Facebook)
    # You can actually add this to Google Authenticator manually to verify!
    MY_TEST_SECRET = "JBSWY3DPEHPK3PXP"

    print("--- 2FA TOTP ENGINE ---")
    print(f"Secret Key: {MY_TEST_SECRET}")

    while True:
        # Generate Code
        code = get_totp_token(MY_TEST_SECRET)

        # Calculate seconds remaining until next change
        seconds_remaining = 30 - (int(time.time()) % 30)

        # Print with overwrite (creating a live updating dashboard effect)
        print(f"\rCurrent Code: {code}  (Updates in: {seconds_remaining}s) ", end="", flush=True)

        time.sleep(1)