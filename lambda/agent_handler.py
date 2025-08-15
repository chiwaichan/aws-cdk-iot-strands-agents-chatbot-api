from strands import Agent, tool
import boto3
from strands_tools import http_request
from typing import Dict, Any
import json
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define an IoT-focused system prompt
IOT_SYSTEM_PROMPT = """You are an IoT device management assistant. You can:

1. Retrieve and analyze IoT device information from AWS IoT Core
2. Provide insights about connected devices and their status
3. Help with IoT device monitoring and management tasks

When working with IoT devices:
- Use the get_all_iot_devices tool to retrieve current device information
- Present device data in a clear, organized format
- Explain device types and their typical functions
- Provide helpful context about IoT device management

Always be helpful in explaining IoT concepts and device information in user-friendly terms.
"""

def handler(event: Dict[str, Any], _context) -> Dict[str, Any]:
    try:
        # Log the incoming event for debugging
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Parse the request body
        body_str = event.get('body', '{}')
        if isinstance(body_str, str):
            body = json.loads(body_str)
        else:
            body = body_str
        
        logger.info(f"Parsed body: {json.dumps(body, default=str)}")
        
        # Extract message and chat history
        message = body.get('message', '')
        chat_history = body.get('chat_history', [])
        
        logger.info(f"Message: {message}")
        logger.info(f"Chat history length: {len(chat_history)}")
        
        # Create the IoT agent
        iot_agent = Agent(
            model="us.amazon.nova-pro-v1:0",
            system_prompt=IOT_SYSTEM_PROMPT,
            tools=[get_all_iot_devices, get_all_iot_thing_types, get_connected_devices, get_vehicle_gps_coordinates],
        )

        # Get response from agent
        response = iot_agent(message)
        
        # Log the agent response
        logger.info(f"Agent response: {response}")
        
        # Prepare the response body
        response_body = {
            'response': str(response),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'success': True,
            'error': None
        }
        
        logger.info(f"Final response body: {json.dumps(response_body, default=str)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Api-Key'
            },
            'body': json.dumps(response_body)
        }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        
        error_response = {
            'response': None,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'success': False,
            'error': str(e)
        }
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_response)
        }


@tool
def get_all_iot_devices() -> list:
    """Retrieves all IoT Things from AWS IoT Core
    
    Returns:
        A list of objects with IoT Thing names and types
    """
    try:
        iot_client = boto3.client('iot')
        response = iot_client.list_things()
        return [{'name': thing['thingName'], 'type': thing.get('thingTypeName')} for thing in response['things']]
    except Exception as e:
        return [{'error': f"Error retrieving IoT things: {str(e)}"}]


@tool
def get_all_iot_thing_types() -> list:
    """Retrieves all IoT Thing Types from AWS IoT Core
    
    Returns:
        A list of IoT Thing Types with their names, descriptions, and attributes
    """
    try:
        iot_client = boto3.client('iot')
        response = iot_client.list_thing_types()
        
        thing_types = []
        for thing_type in response['thingTypes']:
            type_info = {
                'name': thing_type['thingTypeName'],
                'description': thing_type.get('thingTypeDescription', ''),
                'attributes': thing_type.get('thingTypeProperties', {}).get('thingTypeAttributes', [])
            }
            thing_types.append(type_info)
        
        return thing_types
        
    except Exception as e:
        return [{'error': f"Error retrieving IoT thing types: {str(e)}"}]


@tool
def get_connected_devices(thing_type_name: str = None) -> list:
    """Retrieves connected IoT devices using Fleet Indexing
    
    Args:
        thing_type_name: Optional thing type to filter by (e.g., 'VehicleDevice', 'SuitDevice', 'HouseDevice')
        
    Returns:
        List of connected devices with their connectivity status and attributes
    """
    try:
        iot_client = boto3.client('iot')
        
        # Build query string
        query = 'connectivity.connected:true'
        if thing_type_name:
            query += f' AND thingTypeName:{thing_type_name}'
        
        response = iot_client.search_index(queryString=query)
        
        connected_devices = []
        for thing in response['things']:
            device_info = {
                'name': thing['thingName'],
                'type': thing.get('thingTypeName'),
                'connected': thing['connectivity']['connected'],
                'last_seen': thing['connectivity']['timestamp'],
                'attributes': thing.get('attributes', {})
            }
            connected_devices.append(device_info)
        
        return connected_devices
        
    except Exception as e:
        return [{'error': f"Error retrieving connected devices: {str(e)}"}]


@tool
def get_vehicle_gps_coordinates(thing_name: str) -> dict:
    """Retrieves GPS coordinates for an IoT thing of IoT Thing Type 'VehicleDevice'
    
    Args:
        thing_name: The IoT Thing name to query GPS coordinates for
        
    Returns:
        Dictionary with latitude, longitude, altitude, and timestamp
    """
    try:
        # Configuration - these would typically come from environment variables or config
        athena_database_name = 'iot_data'  # Default database name
        vehicle_table_name = 'vehicle_gps_data'  # Default table name
        vehicle_partition_key = 'thing_name'  # Default partition key
        athena_output_s3_bucket = 'iot-athena-query-results'  # Default S3 bucket
        
        athena_client = boto3.client('athena')
        
        query = f"""
        SELECT latitude, longitude, altitude, timestamp
        FROM {athena_database_name}.{vehicle_table_name}
        WHERE {vehicle_partition_key} = '{thing_name}'
        ORDER BY timestamp DESC
        LIMIT 1
        """
        
        s3_output = f's3://{athena_output_s3_bucket}/'
        
        response = athena_client.start_query_execution(
            QueryString=query,
            ResultConfiguration={'OutputLocation': s3_output}
        )
        
        query_execution_id = response['QueryExecutionId']
        
        # Wait for query completion
        while True:
            result = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = result['QueryExecution']['Status']['State']
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
        
        if status == 'SUCCEEDED':
            results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
            if len(results['ResultSet']['Rows']) > 1:  # Skip header row
                data = results['ResultSet']['Rows'][1]['Data']
                return {
                    'latitude': float(data[0]['VarCharValue']),
                    'longitude': float(data[1]['VarCharValue']),
                    'altitude': float(data[2]['VarCharValue']),
                    'timestamp': data[3]['VarCharValue']
                }
        
        return {'error': f'No GPS data found for thing: {thing_name}'}
        
    except Exception as e:
        return {'error': f'Error retrieving GPS coordinates: {str(e)}'}

if __name__ == "__main__":
    # Test event for local development
    test_event = {
        'body': json.dumps({
            'message': 'Tell me about all the iot things',
            'chat_history': []
        })
    }
    
    # Call the handler
    result = handler(test_event, None)
    
    # Print the result
    print("Status Code:", result['statusCode'])
    print("Response Body:")
    response_body = json.loads(result['body'])
    print(json.dumps(response_body, indent=2))