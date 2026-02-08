import time
import os
import totp_engine
import universal_scanner
import database_manager


def menu_scan_new():
    print("\n--- ADD NEW ACCOUNT ---")
    print("1. Webcam Scan")
    print("2. Upload File")
    choice = input("Choice: ")

    extracted_accounts = []

    if choice == '1':
        print("Scanning... (Press 'q' to quit window)")
        extracted_accounts = universal_scanner.run_webcam_scan()

    elif choice == '2':
        extracted_accounts = universal_scanner.select_file_and_scan()

    # --- AUTOMATIC SAVING LOGIC ---
    if extracted_accounts:
        print(f"\n[SUCCESS] Found {len(extracted_accounts)} accounts.")

        for acc in extracted_accounts:
            # Confirm before saving (optional, but good UX)
            print(f"  -> Found: {acc['issuer']} ({acc['name']})")

            # Automatically save to DB
            success = database_manager.add_account(acc['issuer'], acc['name'], acc['secret'])
            if success:
                print("     [SAVED] Added to database.")
            else:
                print("     [SKIP] Account already exists.")

        input("\nPress Enter to return to menu...")
    else:
        print("\n[!] No valid accounts found or operation cancelled.")
        time.sleep(2)


def menu_show_codes():
    accounts = database_manager.get_all_accounts()

    if not accounts:
        print("\nNo accounts found! Go scan some QR codes first.")
        time.sleep(2)
        return

    print("\n--- LIVE 2FA DASHBOARD (Press Ctrl+C to stop) ---")
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{'ISSUER':<15} | {'ACCOUNT':<30} | {'CODE':<10}")
            print("-" * 60)

            for acc in accounts:
                code = totp_engine.get_totp_token(acc['secret'])
                # Truncate long names for display
                name_display = (acc['name'][:27] + '..') if len(acc['name']) > 27 else acc['name']
                print(f"{acc['issuer']:<15} | {name_display:<30} | {code:<10}")

            seconds = 30 - (int(time.time()) % 30)
            bar = "#" * seconds + "-" * (30 - seconds)
            print(f"\nNext update in: {seconds}s  [{bar}]")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    while True:
        # Clear screen for menu
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n=== DESKTOP AUTHENTICATOR ===")
        print("1. Show My 2FA Codes")
        print("2. Add New Account")
        print("3. Exit")

        choice = input("Select: ")

        if choice == '1':
            menu_show_codes()
        elif choice == '2':
            menu_scan_new()
        elif choice == '3':
            break


if __name__ == "__main__":
    main()