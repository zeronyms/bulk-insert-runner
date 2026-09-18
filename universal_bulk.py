import json
import os
import re
import shlex
import time
import requests

CONFIG_FILE = "config.json"
TEMPLATE_FILE = "data_template.json"


def ask_multiline(prompt_text):
    print(prompt_text)
    print("(Type 'END' on a new line and press Enter when finished pasting):\n")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return " ".join(lines)


def parse_curl(curl_cmd):
    try:
        tokens = shlex.split(curl_cmd)
    except Exception:
        # Fallback if character escaping is malformed
        tokens = curl_cmd.split()

    url = None
    method = "POST"
    headers = {}
    data_raw = None

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Extract URL
        if token.startswith("http://") or token.startswith("https://"):
            url = token
        elif token in ("--url",) and i + 1 < len(tokens):
            url = tokens[i + 1]
            i += 1
        # Extract Method
        elif token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 1
        # Extract Headers
        elif token in ("-H", "--header") and i + 1 < len(tokens):
            header_val = tokens[i + 1]
            if ":" in header_val:
                k, v = header_val.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 1
        # Extract Cookie flag
        elif token in ("-b", "--cookie") and i + 1 < len(tokens):
            headers["Cookie"] = tokens[i + 1]
            i += 1
        # Extract Body payload
        elif token in ("-d", "--data", "--data-raw") and i + 1 < len(tokens):
            data_raw = tokens[i + 1]
            i += 1

        i += 1

    if not url:
        raise ValueError("Could not detect endpoint URL from cURL command.")

    # Parse JSON body from cURL if present
    sample_payload = None
    if data_raw:
        try:
            sample_payload = json.loads(data_raw)
        except Exception:
            # Find JSON string via regex if parsing fails
            match = re.search(r"(\{.*\}|\[.*\])", data_raw, re.DOTALL)
            if match:
                sample_payload = json.loads(match.group(1))

    return {
        "url": url,
        "method": method,
        "headers": headers,
        "sample_payload": sample_payload,
    }


def menu_generate_template():
    curl_input = ask_multiline("Paste cURL command from browser:")
    if not curl_input.strip():
        print("cURL command is empty.")
        return

    try:
        parsed = parse_curl(curl_input)

        if not parsed["sample_payload"]:
            print("\n[Warning] JSON payload body not found in cURL.")
            print("Make sure to copy a POST/PUT request that includes form data / payload.")
            return

        # Save request config (URL, method, headers)
        config_data = {
            "url": parsed["url"],
            "method": parsed["method"],
            "headers": parsed["headers"],
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        # Create data template as an array
        sample = parsed["sample_payload"]
        data_template = sample if isinstance(sample, list) else [sample]

        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data_template, f, indent=2)

        print("\nSuccessfully created configuration and template!")
        print(f"1. Headers config saved to  : {CONFIG_FILE}")
        print(f"2. Data template created at : {TEMPLATE_FILE}")
        print("\nNext steps:")
        print(
            f"Open '{TEMPLATE_FILE}', duplicate the objects inside with your desired data, then run Menu 2."
        )

    except Exception as e:
        print(f"\n[Error]: {e}")


def menu_execute_bulk():
    if not os.path.exists(CONFIG_FILE):
        print(
            f"\n[Error] '{CONFIG_FILE}' does not exist yet. Please run Menu 1 first."
        )
        return

    if not os.path.exists(TEMPLATE_FILE):
        print(f"\n[Error] File '{TEMPLATE_FILE}' not found.")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        try:
            items = json.load(f)
            if not isinstance(items, list):
                raise ValueError("JSON file format must be an array []")
        except Exception as e:
            print(f"\n[Error] Invalid '{TEMPLATE_FILE}': {e}")
            return

    print("\n==============================================")
    print(f"Target URL : {config['url']}")
    print(f"Method     : {config['method']}")
    print(f"Total Data : {len(items)} item(s)")
    print("==============================================\n")

    interval_input = input("Enter interval between requests in seconds (default: 2): ").strip()
    try:
        interval = float(interval_input) if interval_input else 2.0
        if interval < 0:
            print("Negative interval not allowed, setting to 0.")
            interval = 0.0
    except ValueError:
        print("Invalid input, defaulting to 2 seconds.")
        interval = 2.0

    print(f"Interval   : {interval} second(s)\n")

    confirm = input("Start executing requests? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    success_count = 0
    fail_count = 0

    session = requests.Session()

    for idx, item in enumerate(items, start=1):
        label = (
            item.get("nama")
            or item.get("name")
            or item.get("kode")
            or item.get("code")
            or f"Row #{idx}"
        )
        print(f"[{idx}/{len(items)}] Sending: {label}...")

        try:
            resp = session.request(
                method=config["method"],
                url=config["url"],
                headers=config["headers"],
                json=item,
                timeout=30,
            )

            status = resp.status_code
            if resp.ok:
                print(f"   Status : {status} (Success)")
                success_count += 1
            else:
                print(f"   Status : {status} (Failed)")
                print(f"   Detail : {resp.text[:180]}...")
                fail_count += 1

                # Auto-stop if session expired
                if status in (401, 419):
                    print(
                        "\n[STOP] Login session / CSRF token expired. Please copy a new cURL and run Menu 1."
                    )
                    break

        except Exception as err:
            print(f"   Network Error: {err}")
            fail_count += 1

        if idx < len(items) and interval > 0:
            print(f"   Waiting {interval} second(s)...\n")
            time.sleep(interval)

    print("\n==============================================")
    print(f"Process Finished! Success: {success_count} | Failed: {fail_count}")
    print("==============================================\n")


def menu_clear_workspace():
    files_to_remove = [CONFIG_FILE, TEMPLATE_FILE, "data.json"]
    existing_files = [f for f in files_to_remove if os.path.exists(f)]

    if not existing_files:
        print("\n[Info] No active configuration or data files found to clear.")
        return

    print("\nThe following files will be deleted:")
    for f in existing_files:
        print(f" - {f}")

    confirm = (
        input("\nAre you sure you want to clear current config and data? (y/n): ")
        .strip()
        .lower()
    )
    if confirm != "y":
        print("Cancelled.")
        return

    for f in existing_files:
        try:
            os.remove(f)
            print(f"Deleted: {f}")
        except Exception as e:
            print(f"Failed to delete {f}: {e}")

    print("\n[Success] Workspace cleared! You can now configure a new API using Menu 1.")


def main():
    while True:
        print("\n==============================================")
        print("         UNIVERSAL BULK INSERT ")
        print("==============================================")
        print("1. Generate Template & Save Auth from cURL")
        print("2. Execute Bulk Insert")
        print("3. Reset / Clear Current API Config & Data")
        print("0. Exit")
        print("==============================================")

        choice = input("Select menu [1/2/3/0]: ").strip()

        if choice == "1":
            menu_generate_template()
        elif choice == "2":
            menu_execute_bulk()
        elif choice == "3":
            menu_clear_workspace()
        elif choice == "0":
            print("Exiting program.")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
