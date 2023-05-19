import re
import os
import subprocess
from datetime import datetime
from influxdb import InfluxDBClient
import logging
from typing import Optional, Dict

# Configure logging
logging.basicConfig(filename='internet_speed.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

def run_speed_test(interface: str) -> Optional[str]:
    try:
        result = subprocess.run(['/usr/bin/speedtest', '--accept-license', '--accept-gdpr', '--interface', interface], capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running speedtest: {e=}")
        return None

def parse_speed_test_output(output: str) -> Optional[Dict[str, float]]:
    ping = re.search('Latency:\s+(.*?)\s', output, re.MULTILINE)
    download = re.search('Download:\s+(.*?)\s', output, re.MULTILINE)
    upload = re.search('Upload:\s+(.*?)\s', output, re.MULTILINE)
    jitter = re.search('Latency:.*?jitter:\s+(.*?)ms', output, re.MULTILINE)

    if ping and download and upload and jitter:
        return {
            "ping": float(ping.group(1)),
            "download": float(download.group(1)),
            "upload": float(upload.group(1)),
            "jitter": float(jitter.group(1))
        }
    else:
        logging.error("Failed to parse speedtest output")
        return None

def write_speed_data(speed_data: Dict[str, float]):
    try:
        logging.info(f"Attempting to write the following data to InfluxDB: {speed_data}")  # Additional logging
        client = InfluxDBClient('localhost', 8086, os.environ['INFLUXDB_USERNAME'], os.environ['INFLUXDB_PASSWORD'], 'internetspeed')
        client.write_points(speed_data)
        logging.info("Speed data written to InfluxDB successfully.")
    except Exception as e:
        logging.error(f"Error writing speed data to InfluxDB: {e=}")

def main():
    interfaces = ["eth0", "wlan0"]  # List of interfaces to test

    for interface in interfaces:
        output = run_speed_test(interface)
        if output:
            speed_data = parse_speed_test_output(output)
            if speed_data is None:  # If parsing fails
                speed_data = {
                    "ping": -1.0,
                    "download": -1.0,
                    "upload": -1.0,
                    "jitter": -1.0
                }
        else:  # If running speedtest fails
            speed_data = {
                "ping": -1.0,
                "download": -1.0,
                "upload": -1.0,
                "jitter": -1.0
            }

        data_point = [{
            "measurement": "internet_speed",
            "tags": {
                "host": "raspberrypi",
                "interface": interface
            },
            "time": datetime.utcnow().isoformat(),
            "fields": speed_data
        }]
        write_speed_data(data_point)

if __name__ == "__main__":
    main()