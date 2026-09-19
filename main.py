import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import (
    CONFIG_FILE,
    CSV_TEMPLATE,
    DATA_FILE_CANDIDATES,
    EXCEL_TEMPLATE,
    JSON_TEMPLATE,
    WORKSPACE_CLEANUP_FILES,
)
from core.curl_parser import (
    detect_array_wrapper,
    detect_url_id_candidates,
    parse_curl,
)
from core.data_handler import (
    export_csv_template,
    export_excel_template,
    export_json_template,
    load_data_file,
)
from core.runner import execute_bulk_requests


def ask_multiline(prompt_text: str) -> str:
    """Prompt user for multiline input until 'END' is typed."""
    print(prompt_text)
    print("(Type 'END' on a new line and press Enter when finished pasting):\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return " ".join(lines)


def select_data_source() -> Path | None:
    """Detect available data files and prompt user if multiple sources exist."""
    existing = [f for f in DATA_FILE_CANDIDATES if f.exists()]
    if not existing:
        return None

    if len(existing) == 1:
        return existing[0]

    print("\nMultiple data files detected:")
    for idx, f in enumerate(existing, start=1):
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  [{idx}] {f.name:<22} (Last modified: {mtime})")

    choice = input(f"\nSelect data source [1-{len(existing)}] (default: 1): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(existing):
            return existing[idx]
    except ValueError:
        pass
    return existing[0]


def menu_generate_template() -> None:
    """Menu 1: Parse cURL and generate configuration + templates."""
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

        sample_payload: Any = parsed["sample_payload"]
        url: str = parsed["url"]
        headers: dict[str, str] = parsed["headers"]

        # Check for nested array wrapper in payload (e.g. {"courses": [...]})
        array_wrapper = detect_array_wrapper(sample_payload)
        mode = "standard"
        array_key: str | None = None
        group_by: str | None = None
        data_template: list[dict[str, Any]] = []

        if array_wrapper:
            arr_key, arr_items = array_wrapper
            print(
                f"\n[Detected Batch Payload] Key '{arr_key}' contains an array of "
                f"{len(arr_items)} item(s)."
            )
            use_grouped = (
                input(f"Enable Grouped Mode? (unpack '{arr_key}' into flat Excel rows) [Y/n]: ")
                .strip()
                .lower()
            )
            if use_grouped != "n":
                mode = "grouped"
                array_key = arr_key
                data_template = [dict(x) for x in arr_items]

        # Check for dynamic ID in URL path (e.g. .../content/LRPN-RZ48G8E4/course)
        referer_val = headers.get("Referer", "") or headers.get("referer", "")
        url_candidates = detect_url_id_candidates(url, referer_val)
        if url_candidates:
            cand_id, suggested_var = url_candidates[0]
            print(f"\n[Detected Dynamic ID in URL]: '{cand_id}'")
            default_var = suggested_var or "id"
            prompt_text = (
                f"Enter parameter name (press Enter for '{default_var}', or 's' to keep static): "
            )
            param_input = input(prompt_text).strip()
            if param_input.lower() != "s":
                var_name = param_input if param_input else default_var
                url = url.replace(cand_id, f"{{{var_name}}}")

                # Also replace placeholder in headers (e.g. Referer)
                for h_key, h_val in headers.items():
                    if cand_id in h_val:
                        headers[h_key] = h_val.replace(cand_id, f"{{{var_name}}}")

                group_by = var_name

                # Prepend the ID variable as the first column in data template
                if data_template:
                    data_template = [{var_name: cand_id, **row} for row in data_template]

        # Fallback template if not grouped
        if not data_template:
            data_template = sample_payload if isinstance(sample_payload, list) else [sample_payload]

        config_data = {
            "url": url,
            "method": parsed["method"],
            "headers": headers,
            "mode": mode,
            "array_key": array_key,
            "group_by": group_by,
            "sample_payload": sample_payload,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        # Export templates
        export_json_template(JSON_TEMPLATE, data_template)
        excel_ok = export_excel_template(EXCEL_TEMPLATE, data_template)
        csv_ok = export_csv_template(CSV_TEMPLATE, data_template)

        print("\n" + "=" * 55)
        print("  CONFIGURATION & TEMPLATES CREATED SUCCESSFULLY!")
        print("=" * 55)
        print(f"1. Target URL template      : {url}")
        print(f"2. Mode                     : {mode.title()}")
        if group_by:
            print(f"   - Group By Column        : {group_by}")
        if array_key:
            print(f"   - Target Array Key       : {array_key}")
        print(f"3. Headers config saved to  : {CONFIG_FILE.name}")
        if excel_ok:
            print(f"4. Excel template created at: {EXCEL_TEMPLATE.name} (⭐ Recommended)")
        if csv_ok:
            print(f"5. CSV template created at  : {CSV_TEMPLATE.name}")
        print(f"6. JSON template created at : {JSON_TEMPLATE.name}")
        print("=" * 55)
        print("\nNext steps:")
        print(f"1. Open '{EXCEL_TEMPLATE.name}' in Microsoft Excel or Google Sheets.")
        if mode == "grouped" and group_by:
            print(
                f"2. Fill in your rows. Items with the same '{group_by}' "
                "will automatically be grouped into one request."
            )
        else:
            print("2. Add or duplicate the data rows you want to insert.")
        print("3. Save the file and run Menu 2 (Execute Bulk Insert).")

    except (ValueError, OSError) as e:
        print(f"\n[Error]: {e}")


def menu_execute_bulk() -> None:
    """Menu 2: Load data and run bulk insert."""
    if not CONFIG_FILE.exists():
        print(f"\n[Error] '{CONFIG_FILE.name}' does not exist yet. Please run Menu 1 first.")
        return

    data_file = select_data_source()
    if not data_file:
        print("\n[Error] No data file found (.xlsx, .csv, or .json).")
        print("Please run Menu 1 to generate template files first.")
        return

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"\n[Error] Failed to read '{CONFIG_FILE.name}': {e}")
        return

    sample_payload = config.get("sample_payload")
    mode = config.get("mode", "standard")
    array_key = config.get("array_key")
    group_by = config.get("group_by")

    try:
        print(f"\nLoading data from: {data_file.name}...")
        items = load_data_file(data_file, sample_payload)
        if not items:
            print(f"\n[Warning] No data rows found in '{data_file.name}'.")
            return
    except Exception as e:
        print(f"\n[Error] Failed to read '{data_file.name}': {e}")
        return

    print("\n==============================================")
    print(f"Data Source: {data_file.name}")
    print(f"Target URL : {config['url']}")
    print(f"Method     : {config['method']}")
    if mode == "grouped" and array_key:
        if group_by:
            unique_groups = len(
                {
                    str(it.get(group_by, "")).strip()
                    for it in items
                    if str(it.get(group_by, "")).strip()
                }
            )
            print(f"Mode       : Grouped by '{group_by}' into '{array_key}'")
            print(f"Total Data : {len(items)} row(s) -> {unique_groups} request(s)")
        else:
            print(f"Mode       : Packed into array '{array_key}'")
            print(f"Total Data : {len(items)} row(s) -> 1 request")
    else:
        print("Mode       : Standard (1 row = 1 request)")
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

    success_count, fail_count = execute_bulk_requests(
        url=config["url"],
        method=config["method"],
        headers=config["headers"],
        items=items,
        interval=interval,
        group_by=group_by,
        array_key=array_key,
    )

    print("\n==============================================")
    print(f"Process Finished! Success: {success_count} | Failed: {fail_count}")
    print("==============================================\n")


def menu_clear_workspace() -> None:
    """Menu 3: Clear workspace configurations and templates."""
    existing_files = [f for f in WORKSPACE_CLEANUP_FILES if f.exists()]

    if not existing_files:
        print("\n[Info] No active configuration or data files found to clear.")
        return

    print("\nThe following files will be deleted:")
    for f in existing_files:
        print(f" - {f.name}")

    confirm = (
        input("\nAre you sure you want to clear current config and data? (y/n): ").strip().lower()
    )
    if confirm != "y":
        print("Cancelled.")
        return

    for f in existing_files:
        try:
            f.unlink()
            print(f"Deleted: {f.name}")
        except OSError as e:
            print(f"Failed to delete {f.name}: {e}")

    print("\n[Success] Workspace cleared! You can now configure a new API using Menu 1.")


def main() -> None:
    """Main CLI entry loop."""
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
