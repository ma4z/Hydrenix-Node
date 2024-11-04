from flask import Flask, jsonify, request, abort
import json
import argparse
import os
import subprocess
import asyncio
import random
import string

app = Flask(__name__)

config_file_path = 'config.json'
database_file = 'vms.txt'

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

def add_to_database(user, container_name, ssh_command):
    """Add server details to the database."""
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}\n")

async def capture_ssh_command(process):
    """Capture the SSH session command from tmate output."""
    max_retries = 30  # Wait up to 30 seconds
    ssh_command = None  # To store the relevant SSH command
    for _ in range(max_retries):
        line = await process.stdout.readline()
        if line:
            decoded_line = line.decode().strip()
            print(f"tmate output: {decoded_line}")  # Log for debugging

            if "ssh " in decoded_line and "ro-" not in decoded_line:
                ssh_command = decoded_line
            if ssh_command:
                break
        await asyncio.sleep(1)
    return ssh_command

async def create_docker_server(ram, cores, user_id):
    """Create a new Docker server and return the container ID."""
    image = "ghcr.io/ma4z-spec/hydren-vm:latest"
    try:
        container_id = subprocess.check_output([ 
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL",
            "--memory", ram, "--cpus", str(cores), image
        ]).strip().decode('utf-8')
    except subprocess.CalledProcessError as e:
        return None, str(e)

    try:
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        subprocess.run(["docker", "kill", container_id])
        subprocess.run(["docker", "rm", container_id])
        return None, str(e)

    ssh_session_line = await capture_ssh_command(exec_cmd)
    if ssh_session_line:
        return container_id, ssh_session_line
    else:
        subprocess.run(["docker", "kill", container_id])
        subprocess.run(["docker", "rm", container_id])
        return None, "Failed to capture SSH command."

def generate_random_user_id(length=8):
    """Generate a random user ID consisting of letters and digits."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def require_auth(f):
    def wrapper(*args, **kwargs):
        api_key = request.args.get('api_key')  # Get API key from query parameters
        if not authenticate(api_key):
            abort(401)  # Unauthorized
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__  # Preserve the original function name
    return wrapper

@app.route('/vm/create', methods=['GET'])
@require_auth
def create_server():
    ram = request.args.get('ram')
    cores = request.args.get('cores')

    if not ram or not cores:
        return {"error": "Missing parameters: ram and cores are required."}, 400

    user_id = "User"

    container_id, ssh_command = asyncio.run(create_docker_server(ram, cores, user_id))

    if container_id:
        add_to_database(user_id, container_id, ssh_command)
        return {
            "message": "Server created successfully.",
            "container_id": container_id,
            "ssh_command": ssh_command
        }, 200
    else:
        return {"error": f"Error creating Docker container: {ssh_command}"}, 500

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
