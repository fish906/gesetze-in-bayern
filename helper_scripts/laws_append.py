import yaml
import os

def append_law_to_yaml(file_path):
    print("Please provide the details for the new law entry:")

    double_quote = "
    law_id = double_quote + input("Enter the ID (e.g., BayVersG): ") + double_quote
    name = input("Enter the Name (e.g., Bayrisches Versammlungsgesetz): ")
    prefix = input("Enter the Prefix (e.g., BayVersG): ")
    end = input("Enter the End value for numbering: ")

    new_law_entry = {
        "id": law_id,
        "name": name,
        "numbering": {
            "type": "article",
            "prefix": prefix,
            "start": 1,
            "end": int(end)
        }
    }

    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                if data is None:
                    data = {}
        except yaml.YAMLError as e:
            print(f"Error parsing existing YAML file: {e}")
            print("Attempting to create a new file or overwrite existing content if it's invalid.")
            data = {}
        except FileNotFoundError:
            print(f"File not found at {file_path}. A new file will be created.")
    else:
        print(f"File not found at {file_path}. A new file will be created.")

    if "laws" not in data or not isinstance(data["laws"], list):
        data["laws"] = []

    data["laws"].append(new_law_entry)

    try:
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, indent=2)
        print(f"\nSuccessfully appended the new law entry to '{file_path}'.")
    except IOError as e:
        print(f"Error writing to file: {e}")
    except yaml.YAMLError as e:
        print(f"Error dumping YAML data: {e}")

if __name__ == '__main__':
    yaml_file_name = 'test.yml'

    while True:
        append_law_to_yaml(yaml_file_name)

        user_choice = input('\nAdd another entry? (y/n): ').lower()

        if user_choice == 'yes':
            continue

        else:
            print('Done!\n')
            break
