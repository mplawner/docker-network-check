import subprocess
import configparser
import requests

# Read configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')
excluded_containers = config.get('Containers', 'excluded_containers', fallback='').split(', ')
included_containers = config.get('Containers', 'included_containers', fallback='').split(', ')
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
except ValueError:
    notify_telegram  = False
bot_token = config.get('Telegram', 'bottoken', fallback='')
chat_id = config.get('Telegram', 'chatid', fallback='')

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
    test_file_url = "http://ipv4.download.thinkbroadband.com/5MB.zip"  # Example URL, replace with your chosen test file
    curl_command = f"curl -s -w '%{{time_total}}' -o /dev/null {test_file_url}"
    try:
        output = subprocess.check_output(f"docker exec {container_id} /bin/sh -c '{curl_command}'", shell=True, stderr=subprocess.STDOUT)
        time_taken = float(output.decode().strip())
        if time_taken > 0:
            # Assuming a 5 MB file, convert time taken from seconds to download speed in Mbps
            download_speed_mbps = (5 * 8) / time_taken
            return f"Download Speed: {download_speed_mbps:.2f} Mbps"
        else:
            return "Failed to calculate download speed: Time taken is 0"
    except subprocess.CalledProcessError as e:
        return f"Failed to perform speed test: {e.output.decode()}"

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, data=data)
    if not response.ok:
        print(f"Failed to send message: {response.text}")
    #return response.json()

# Main logic
if __name__ == "__main__":
    host_ip = get_host_external_ip()
    container_ids = get_container_ids()

    for container_id in container_ids:
        container_name = get_container_name(container_id)

        if not is_container_selected(container_name, container_id):
            if verbose:
                print(f"Skipping container: {container_name}")
            continue

        if not curl_available_in_container(container_id):
            if verbose:
                print(f"curl not found in {container_name}, skipping...")
            continue

        container_ip = get_container_external_ip(container_id)

        if container_ip:
            on_main_ip = "True" if container_ip == host_ip else "False"
            message = f"Container Name: {container_name}\nOn Main IP: {on_main_ip}\nExternal IP: {container_ip}"
            if runspeedtest:
                speed_test_result = download_speed_test(container_id)
                message += f"\nNetwork Speed: {speed_test_result}"
            if notify_telegram:
                send_telegram_message(bot_token, chat_id, message)
            print(message)
        else:
            print(f"Failed to get external IP for container: {container_name}")

