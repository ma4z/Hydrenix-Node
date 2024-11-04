from flask import Flask, jsonify, request, abort
import json
import argparse
import os

app = Flask(__name__)

config_file_path = 'config.json'

# Default configuration
default_config = {
    "api_key": "your_api_key_here"
}

# Check if config.json exists, if not, create it
if not os.path.isfile(config_file_path):
    with open(config_file_path, 'w') as config_file:
        json.dump(default_config, config_file, indent=4)
        print("config.json created with default values.")

# Load the configuration from config.json
if os.path.exists(config_file_path):
    with open(config_file_path) as config_file:
        config = json.load(config_file)
else:
    config = {"api_key": None}

# Function to authenticate based on API key
def authenticate(api_key):
    return config.get("api_key") == api_key

def require_auth(f):
    def wrapper(*args, **kwargs):
        api_key = request.args.get('api_key')  # Get API key from query parameters
        if not authenticate(api_key):
            abort(401)  # Unauthorized
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__  # Preserve the original function name
    return wrapper

@app.route('/status', methods=['GET'])
@require_auth
def status():
    return jsonify({"status": "online"})

def save_key(key):
    config["api_key"] = key
    with open(config_file_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run the Flask application.')
    parser.add_argument('--key', type=str, help='API key to set in config.json')

    args = parser.parse_args()

    if args.key:
        save_key(args.key)
        print(f"API Key Set: {args.key}")
    else:
        # Start the Flask app only if no key is provided
        app.run(host='0.0.0.0', port=3002)
