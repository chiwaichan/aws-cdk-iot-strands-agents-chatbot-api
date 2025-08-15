#!/usr/bin/env python3
import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError

def get_api_gateway_info(profile_name):
    """Retrieve API Gateway URL and API key for a given AWS profile"""
    try:
        session = boto3.Session(profile_name=profile_name)
        apigateway = session.client('apigateway')
        
        # Get REST APIs
        apis = apigateway.get_rest_apis()
        
        if not apis['items']:
            return None, None, "No REST APIs found"
        
        # Get the first API (modify logic if you need specific API)
        api = apis['items'][0]
        api_id = api['id']
        api_name = api['name']
        
        # Construct API Gateway URL
        region = session.region_name or 'us-east-1'
        api_url = f"https://{api_id}.execute-api.{region}.amazonaws.com"
        
        # Get API keys
        api_keys = apigateway.get_api_keys()
        api_key_value = None
        
        if api_keys['items']:
            # Get the first API key value
            key_id = api_keys['items'][0]['id']
            key_details = apigateway.get_api_key(apiKey=key_id, includeValue=True)
            api_key_value = key_details['value']
        
        return api_url, api_key_value, None
        
    except NoCredentialsError:
        return None, None, f"No credentials found for profile: {profile_name}"
    except ClientError as e:
        return None, None, f"AWS error: {e.response['Error']['Message']}"
    except Exception as e:
        return None, None, f"Error: {str(e)}"

def main():
    profiles = ['default', 'prod']
    
    for profile in profiles:
        print(f"\n=== Profile: {profile} ===")
        api_url, api_key, error = get_api_gateway_info(profile)
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"API Gateway URL: {api_url}")
            print(f"API Key: {api_key if api_key else 'No API key found'}")

if __name__ == "__main__":
    main()