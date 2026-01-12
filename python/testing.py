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



template = ( dict, {
             'blocks'  : ( list, ( dict, { 'name' : str, 'type' : str } ) ),
             'signals' : ( list, ( dict, { 'name' : str, 'type' : ( str, [ 'bit', 's32', 'u32', 'float' ] ), 'value' : None, 'links' : ( list, str ) } ) ),
             'threads' : ( list, ( dict, { 'name' : str, 'period' : int, 'runs' : ( list, str ) } ) ) } )

def check_type(name, item, pattern):
    '''
    checks the type of a data item, which can be a complex nexted data structure

    :param name: name of item; will be printed in error messages
    :param item: item to be checked
    :param pattern: pattern to check 'item' against, can be one of the following:
        None: no type checking is applied
        a single type: checks that 'item' is an instance of type
        a tuple consisting of a type followed by type-specific data, as follows:
            str followed by list of strings: 'item' must be a string in the list
            list followed by a sub-pattern: 'item' must be a list, and the
                sub-pattern is recursively applied to each list element
            dict followed by a dict of key:sub-pattern pairs; 'item' must be
                a dict containing all of and only the specified keys, and each
                key's sub-pattern is recursively applied to that key's value
    '''
    if pattern == None:
        return True
    if not isinstance(pattern, tuple):
        # simple pattern, does type match only
        if not isinstance(item, pattern):
            print(f"'{name}' is '{item}', expected {pattern}")
            return False
    else:
        # tuple pattern
        type = pattern[0]
        if type == str:
            # check against list of allowed strings
            allowed = pattern[1]
            if not item in allowed:
                print(f"'{name}' is '{item}', expected one of {allowed}")
                return False
        elif type == list:
            if not isinstance(item, list):
                print(f"'{name}' is '{item}', expected {list}")
                return False
            subpattern = pattern[1]
            for index, subitem in enumerate(item):
                if not check_type(f"{name}[{index}]", subitem, subpattern):
                    return False
        elif type == dict:
            if not isinstance(item, dict):
                print(f"'{name}' is '{item}', expected {dict}")
                return False
            patternkeys = set(pattern[1].keys())
            itemkeys = set(item.keys())
            missing = patternkeys - itemkeys
            if missing:
                print(f"'{name}' missing required keys {missing}")
                return False
            unexpected = itemkeys - patternkeys
            if unexpected:
                print(f"'{name}' contains unexpected keys {unexpected}")
                return False
            for key, subitem in item.items():
                if not check_type(f"{key}", subitem, pattern[1][key]):
                    print(f"  in {name}")
                    return False
        else:
            print(f"unknown pattern {pattern}")
            return False
    return True


# template = ( dict, { "foo" : str, "bar" : ( str, [ "hello", "world" ]) } )
# object = { 'bar': "hello", 'foo': "world!" }

# print(f"{template=}")
# print(f"{object=}")
# print(f"{check_type("toplevel", object, template)=}")



print(f"{template=}")
fd = read_json_file("sample.json")
print(f"{fd=}")
print(f"{check_type('toplevel', fd, template)=}")

