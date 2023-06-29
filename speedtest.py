import re
import os
import asyncio
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
import logging
from typing import Optional, Dict
from influxdb_client.client.write_api import SYNCHRONOUS

# Configure logging to write INFO level logs to a file 'internet_speed.log' with specified formatting
logging.basicConfig(filename='internet_speed.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

# Asynchronous function to run the speedtest-cli command and return the output
async def run_speed_test(interface: str) -> Optional[str]:
    try:
        # Use asyncio's version of subprocess.run
        result = await asyncio.create_subprocess_exec(
            '/usr/bin/speedtest', '--accept-license', '--accept-gdpr', '--interface', interface,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        
        stdout, stderr = await result.communicate()
        return stdout.decode()
    except Exception as e:
        logging.error(f"Error running speedtest: {e=}")
        return None

# Function to parse the output of the speedtest-cli command
def parse_speed_test_output(output: str) -> Optional[Dict[str, float]]:
    ping = re.search('Latency:\s+(.*?)\s', output, re.MULTILINE)
    download = re.search('Download:\s+(.*?)\s', output, re.MULTILINE)
    upload = re.search('Upload:\s+(.*?)\s', output, re.MULTILINE)
    jitter = re.search('Latency:.*?jitter:\s+(.*?)ms', output, re.MULTILINE)

    try:
        # Convert results to float, if any of the tests failed, set their result as -1.0
        if ping and ping.group(1) != "FAILED":
            ping = float(ping.group(1))
        else:
            ping = -1.0
        if download and download.group(1) != "FAILED":
            download = float(download.group(1))
        else:
            download = -1.0
        if upload and upload.group(1) != "FAILED":
            upload = float(upload.group(1))
        else:
            upload = -1.0
        if jitter and jitter.group(1) != "FAILED":
            jitter = float(jitter.group(1))
        else:
            jitter = -1.0
        # Return results as a dictionary
        return {
            "ping": ping,
            "download": download,
            "upload": upload,
            "jitter": jitter
        }
    except ValueError as e:
        logging.error(f"Failed to parse speedtest output: {e}")
        return None

# Create an InfluxDBClient instance
client = InfluxDBClient(url='http://localhost:8086', token=f'{os.environ["INFLUXDB_USERNAME"]}:{os.environ["INFLUXDB_PASSWORD"]}', org='-')

# Function to write speedtest data to InfluxDB
def write_speed_data(speed_data):
    try:
        logging.info(f"Attempting to write the following data to InfluxDB: {speed_data}")
        with client.write_api(write_options=SYNCHRONOUS) as write_api:
            write_api.write('internetspeed', org='-', record=speed_data)
        logging.info("Speed data written to InfluxDB successfully.")
    except Exception as e:
        logging.error(f"Error writing speed data to InfluxDB: {e=}")

# Main function
async def main():
    # Define network interfaces to run the speedtest on
    interfaces = ["eth0", "wlan0"]  
    
    # Create a list of tasks (running speedtest on each interface)
    tasks = [run_speed_test(interface) for interface in interfaces]

    # Use asyncio.gather to run them all concurrently
    outputs = await asyncio.gather(*tasks)

    # Loop over the output from each task
    for i, output in enumerate(outputs):
        if output:
            speed_data = parse_speed_test_output(output)
            # If parsing fails, set all results as -1.0
            if speed_data is None:  
                speed_data = {
                    "ping": -1.0,
                    "download": -1.0,
                    "upload": -1.0,
                    "jitter": -1.0
                }
        else:  # If running speedtest fails, set all results as -1.0
            speed_data = {
                "ping": -1.0,
                "download": -1.0,
                "upload": -1.0,
                "jitter": -1.0
            }

        # Create a data point and write it to InfluxDB
        data_point = Point("internet_speed").tag("host", "raspberrypi").tag("interface", interfaces[i]).time(datetime.utcnow(), WritePrecision.NS).field("ping", speed_data["ping"]).field("download", speed_data["download"]).field("upload", speed_data["upload"]).field("jitter", speed_data["jitter"])
        write_speed_data(data_point)

# Run the main function when the script is called directly
if __name__ == "__main__":
    asyncio.run(main())




