import json


def read_json_file(filename):
    filedata = {}
    try:
        with open(filename, 'r', encoding='utf-8') as jsonfile:
            filedata = json.load(jsonfile)
    except FileNotFoundError:
        print(f"Warning: file '{filename}' was not found.")
    except OSError as e:
        print(f"Error reading '{filename}': {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding '{filename}': {e}")
    return filedata

def check_lists(provided, required, optional, message):
    missing = set(required) - set(provided)
    allowed = required + optional
    unexpected = set(provided) - set(allowed)
    seen = set()
    duplicates = []
    for item in provided:
        if item in seen:
            if item not in duplicates:
                duplicates.append(item)
        else:
            seen.add(item)
    if missing:
        print(f"{message}: missing item(s): {missing}")
    if unexpected:
        print(f"{message}: unexpected item(s): {unexpected}")
    if duplicates:
        print(f"{message}: duplcate item(s): {duplicates}")
    if missing or unexpected or duplicates:
        return False
    return True

def validate_block(block_dict):
    required_keys=["name", "type"]
    optional_keys=[]
    return check_lists(block_dict.keys(), required_keys, optional_keys, "block")

def validate_signal(signal_dict):
    required_keys=["name", "type", "links"]
    optional_keys=["value"]
    return check_lists(signal_dict.keys(), required_keys, optional_keys, "signal")

def validate_thread(thread_dict):
    required_keys=["name", "runs"]
    optional_keys=["period"]
    return check_lists(thread_dict.keys(), required_keys, optional_keys, "thread")

def validate_structure(model):
    if not isinstance(model, dict):
        print(f"toplevel should be dict, not {type(model)}")
        return False
    validators = { "blocks" : validate_block, "signals" : validate_signal, "threads": validate_thread }
    seen=set()
    duplicates=[]
    if not check_lists(model.keys(), list(validators.keys()), [], "toplevel"):
        return False
    for key, value in model.items():
        if not isinstance(value, list):
            print(f"'{key} should be list, not {type(value)}")
            return False
        for item in value:
            if not isinstance(item, dict):
                print(f"{key} list item should be dict, not {type(item)}")
                return False
            if not validators[key](item):
                return False
            if item["name"] in seen:
                if not item["name"] in duplicates:
                    duplicates.append(item["name"])
            else:
                seen.add(item["name"])
    if duplicates:
        print(f"duplicated name(s): {duplicates}")
        return False
    print(f"{seen=}")
    return True



fd = read_json_file("sample.json")
#print(f"{fd=}")
print(f"{validate_structure(fd)=}")

