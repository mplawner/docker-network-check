import argparse
import subprocess
import configparser
import requests
import logging

# Set up argument parsing
parser = argparse.ArgumentParser(description='Run the VPN health check script with a specified configuration file.')
parser.add_argument('--config', type=str, required=True, help='Path to the configuration file')
args = parser.parse_args()

# Read configuration from the specified config.ini file
config = configparser.ConfigParser()
config.read(args.config)

# Configure logging
log_file = config.get('Settings', 'logfile', fallback='vpnhealth.log')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

excluded_containers = config.get('Containers', 'excluded_containers', fallback='').split(', ')
included_containers = config.get('Containers', 'included_containers', fallback='').split(', ')

test_file_url = config.get('Settings', 'test_file_url', fallback='http://ipv4.download.thinkbroadband.com/5MB.zip') 

try:
    verbose = config.getboolean('Settings', 'verbose', fallback=False)
except ValueError:
    verbose = False
try:
    runspeedtest  = config.getboolean('Settings', 'speedtest', fallback=False)
except ValueError:
    runspeedtest = False
try:
    notify_telegram  = config.getboolean('Settings', 'telegram_enabled')
    bot_token = config.get('Telegram', 'bottoken', fallback='')
    chat_id = config.get('Telegram', 'chatid', fallback='')
except ValueError:
    notify_telegram  = False
try:
    notify_prowl  = config.getboolean('Settings', 'prowl_enabled')
    prowl_api_key = config.get('Prowl', 'apikey', fallback='')
except ValueError:
    notify_prowl = False

# Function to get the host's external IP address
def get_host_external_ip():
    return subprocess.getoutput("curl --silent http://ipinfo.io/ip")

# Adjust the check to account for included containers
def is_container_selected(container_name, container_id):
    if included_containers[0]:  # Check if the included_containers list is not empty
        return container_name in included_containers or container_id in included_containers
    else:  # If included_containers is empty, revert to exclusion logic
        return not (container_name in excluded_containers or container_id in excluded_containers)

# Function to get the list of running Docker container IDs
def get_container_ids():
    return subprocess.getoutput("docker ps -q").split()

# Function to get the container's name by its ID
def get_container_name(container_id):
    return subprocess.getoutput(f"docker inspect --format='{{{{.Name}}}}' {container_id}").strip('/')

# Function to check if curl is available in the container
def curl_available_in_container(container_id):
    result = subprocess.run(["docker", "exec", container_id, "which", "curl"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

# Function to get the container's external IP by executing a curl command within the container
def get_container_external_ip(container_id):
    try:
        # Set a reasonable timeout for the curl command, e.g., 10 seconds
        output = subprocess.check_output(f"docker exec {container_id} curl --silent --max-time 10 http://ipinfo.io/ip", shell=True, stderr=subprocess.STDOUT)
        return output.decode().strip()
    except subprocess.CalledProcessError as e:
        # Check if the error was due to a timeout or another issue
        if "timed out" in e.output.decode().lower():
            return "Timeout occurred while trying to get external IP"
        else:
            return "Error occurred while trying to get external IP"

def download_speed_test(container_id):
    curl_command = f"curl -s -w '%{{time_total}},%{{size_download}}' -o /dev/null {test_file_url}"

    # Determine if the command should run on the host or within a Docker container
    command_to_run = curl_command if container_id == "0" else f"docker exec {container_id} /bin/sh -c '{curl_command}'"

    try:
        output = subprocess.check_output(command_to_run, shell=True, stderr=subprocess.STDOUT)
        time_taken_str, size_download_str = output.decode().strip().split(',')
        time_taken = float(time_taken_str)
        size_download_bytes = float(size_download_str)
        if time_taken > 0:
            # Convert time taken from seconds to download speed in Mbps
            download_speed_mbps = (size_download_bytes * 8) / (time_taken * 1024 * 1024)
            #print (f"Size of Download in bytes: {size_download_bytes} and Time Taken: {time_taken}")
            return f"{download_speed_mbps:.2f} Mbps"
        else:
            return "Failed"
    except subprocess.CalledProcessError as e:
        return f"Failed to perform speed test: {e.output.decode()}"

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, data=data)
    if not response.ok:
        logging.error(f"Failed to send message: {response.text}")

def send_prowl_notification(api_key, message):
    url = "https://api.prowlapp.com/publicapi/add"
    params = {
        "apikey": api_key,
        "application": "Docker Monitor",
        "event": "Container Status",
        "description": message
    }
    response = requests.post(url, params=params)
    if not response.ok:
        logging.error(f"Failed to send Prowl notification: {response.text}")

# Main logic
if __name__ == "__main__":
    host_ip = get_host_external_ip()
    container_ids = get_container_ids()

    for container_id in container_ids:
        container_name = get_container_name(container_id)

        if not is_container_selected(container_name, container_id):
            if verbose:
                logging.info(f"Skipping container: {container_name}")
            continue

        if not curl_available_in_container(container_id):
            if verbose:
                logging.info(f"curl not found in {container_name}, skipping...")
            continue

        container_ip = get_container_external_ip(container_id)

        if container_ip:
            on_vpn = "False" if container_ip == host_ip else "True"
            # Multi-line message for notifications
            message = f"Container Name: {container_name}\nVPN Active: {on_vpn}\nExternal IP: {container_ip}"
            
            if runspeedtest:
                speed_test_result = download_speed_test(container_id)
                host_speedtest = download_speed_test("0")  # Assuming "0" is used for the host
                message += f"\nNetwork Speed: {speed_test_result}\nHost Network Speed: {host_speedtest}"

            # Single-line message for logging
            log_message = message.replace('\n', ' | ')  # Use ' | ' as a delimiter to separate message parts in the log

            if notify_telegram:
                send_telegram_message(bot_token, chat_id, message)  # Use the original multi-line message for Telegram
            if notify_prowl:
                send_prowl_notification(prowl_api_key, message)  # Use the original multi-line message for Prowl

            logging.info(log_message)  # Log the single-line version
        else:
            logging.error(f"Failed to get external IP for container: {container_name}")
