# Docker Container Monitor and Notifier

This script monitors Docker containers, checks their external IP addresses, identifies if they are running over a VPN, measures their internet speed, and sends notifications via various applications with the results.

## Prerequisites

- Python 3
- Docker
- `requests` library for Python
- Telegram Bot Token and Chat ID (Optional)
- Prowl API (Optional)

## Setup

### 1. Clone the Repository

Clone this repository to your local machine or server where Docker is running.

```bash
git clone https://github.com/mplawner/docker-network-check.git
cd docker-network-check
```

### 2. Create a Virtual Environment

Create a Python virtual environment to isolate the project dependencies.

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages in the virtual environment.

```bash
pip install requests
```

### 4. Configuration

Edit the `config.ini` file to include your Docker container preferences, Telegram Bot Token, and Chat ID.

```ini
[Containers]
excluded_containers = container1, container2
included_containers =

[Settings]
logfile = vpnhealth.log
verbose = true
speedtest = true
telegram_enabled = true
prowl_enabled = true

[Telegram]
bottoken = YOUR_BOT_TOKEN_HERE
chatid = YOUR_CHAT_ID_HERE

[Prowl]
apikey = YOUR_PROWL_API_KEY
```

### 5. Running the Script

Run the script manually to ensure it works as expected.

```bash
python ./vpnhealth.py --config config.ini
```

Remember, to deactivate the virtual environment when you are done, use the command:

```
deactivate
```

### 6. Setting up a Cron Job

Open your crontab file:

```bash
crontab -e
```

Add a line to execute the script at your desired frequency. For example, to run it hourly:

```cron
0 * * * * /path/to/your/venv/bin/python /path/to/your/script.py --config /path/to/your/config.ini
```

Replace `/path/to/your/venv/bin/python`, `/path/to/your/script.py`, and `/path/to/your/config.ini` with the full paths to your Python virtual environment's interpreter, your script, and your config.ini file respectively.

## Troubleshooting

Ensure that your Docker containers have `curl` installed if you're checking external IPs or measuring internet speed. Check the log file specified in the cron job for errors or messages.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.

