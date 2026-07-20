import os
import yaml
import json
import pandas as pd
from dotenv import load_dotenv


def read_env() -> dict:
    """
    Loads environment variables from .env file and returns
    the relevant config as a dictionary.
    """
    load_dotenv(override=True)
    return {
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
    }


def read_yml_file(file_path: str) -> dict:
    """
    Reads a YAML file and returns its contents as a dictionary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")

    with open(file_path, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ValueError(f"Error reading YAML file: {e}")


def read_json_file(file_path: str) -> dict:
    """
    Reads a JSON file and returns its contents as a dictionary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")

    with open(file_path, 'r') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error reading JSON file: {e}")


def read_txt_file(file_path: str) -> str:
    """
    Reads a plain text file and returns its contents as a string.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")

    with open(file_path, 'r') as file:
        return file.read()


def write_json_file(file_path: str, data: dict, indent: int = 2) -> str:
    """
    Writes a dictionary to a JSON file, creating parent directories if needed.
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=indent, default=str)
    print(f"✓ JSON saved: {file_path}")
    return file_path


def write_csv_file(file_path: str, df: pd.DataFrame, index: bool = False) -> str:
    """
    Writes a pandas DataFrame to a CSV file, creating parent directories if needed.
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    df.to_csv(file_path, index=index)
    print(f"✓ CSV saved: {file_path}")
    return file_path


def write_txt_file(file_path: str, content: str) -> str:
    """
    Writes plain text content to a file, creating parent directories if needed.
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(content)
    print(f"✓ Text saved: {file_path}")
    return file_path