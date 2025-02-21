import requests
import json
import os
import hashlib
import base64
import time
import hmac
from influxdb import InfluxDBClient
import pprint
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize InfluxDB clients
campus_client = InfluxDBClient(host=os.getenv('INFLUXDB_HOST'), port=8086, username=os.getenv('NETWORK_DB_USER'), password=os.getenv('NETWORK_DB_PASS'), database=os.getenv('INFLUXDB_DB'),ssl=True,verify_ssl=True)
network_client = InfluxDBClient(host=os.getenv('INFLUXDB_HOST'), port=8086, username=os.getenv('NETWORK_DB_USER'), password=os.getenv('NETWORK_DB_PASS'), database=os.getenv('INFLUXDB_DB'),ssl=True,verify_ssl=True)

def get_widget_data(widget_id):
    """Fetch data for a specific widget."""
    print(f"Fetching data for widget ID: {widget_id}")
    
    http_verb = 'GET'
    resource_path = f'/dashboard/widgets/{widget_id}/data'
    url = f'https://{os.getenv("Company")}.logicmonitor.com/santaba/rest{resource_path}'
    epoch = str(int(time.time() * 1000))

    # Concatenate request details for HMAC
    request_vars = f"{http_verb}{epoch}{resource_path}"
    
    # Create HMAC signature
    digest = hmac.new(
        os.getenv('AccessKey').encode('utf-8'),
        msg=request_vars.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    signature = base64.b64encode(digest.encode('utf-8')).decode('utf-8')
    auth = f'LMv1 {os.getenv("AccessId")}:{signature}:{epoch}'
    
    headers = {'Content-Type': 'application/json', 'Authorization': auth}

    # Perform the GET request
    response = requests.get(url, headers=headers)

    # Check for successful response
    if response.status_code != 200:
        print(f"Error fetching widget data: {response.status_code} - {response.text}")
        return None
    
    return response.json()

def main():
    """Main function to process widget data and write to InfluxDB."""
    metric_data = []
    widget_ids = [12820, 12818, 12821, 13131]
    gateway_map = {
        12820: 'aws_gw_west-percent',
        12818: 'azure_gw_west-percent',
        12821: 'autodesk_gw_west-percent',
        13131: 'cloud-fabric_gw_west-percent',
    }

    for widget_id in widget_ids:
        gateway = gateway_map.get(widget_id)
        response = get_widget_data(widget_id)

        if response is None:
            continue  # Skip processing if there was an error

        print(response)

        for metric in response.get("data", {}).get("rows", []):
            try:
                metric_json = {
                    "measurement": "multicloud_link_us-west-percent",
                    "tags": {
                        "gateway": gateway
                    },
                    "fields": {
                        "in": metric['cells'][1]['value'],
                        "out": metric['cells'][0]['value']
                    }
                }
                metric_data.append(metric_json)
                print(metric_json)
            except Exception as e:
                print('Error processing metric: ', e)

    # Write collected metrics to InfluxDB
    if metric_data:
        campus_client.write_points(metric_data)
        network_client.write_points(metric_data)
    else:
        print("No metrics to write to InfluxDB.")

if __name__ == "__main__":
    main()

