import backoff
import openai
import requests
import json

# Try importing from various possible locations based on OpenAI SDK version
try:
    # For newer OpenAI SDK versions
    from openai import BadRequestError, RateLimitError, APIError, APIConnectionError
except ImportError:
    try:
        # For slightly older OpenAI SDK versions
        from openai.types.error import APIError, APIConnectionError, RateLimitError
        from openai.types.error import BadRequestError, AuthenticationError, NotFoundError
    except ImportError:
        # For much older versions
        BadRequestError = Exception
        RateLimitError = Exception
        APIError = Exception
        APIConnectionError = Exception
'sk-yBXqyyoFm78JSPB5MtrW6HZOT9Cu8yRVqGakSJQeh1fOEGzN'

class OpenAI:
    def __init__(self, model, api_key, temperature=0):
        try:
            # For newer versions of the API
            self.client = openai.OpenAI(api_key=api_key, base_url="https://api.chatanywhere.tech/v1")
        except (AttributeError, TypeError):
            # For older versions of the API
            openai.api_key = api_key
            openai.api_base = "https://api.chatanywhere.tech/v1"

            self.client = openai
            
        self.model = model
        self.temperature = temperature

    @backoff.on_exception(backoff.expo, 
                         Exception,  # Catch all exceptions for maximum compatibility
                         max_tries=5, factor=2, max_time=60)
    def create_chat_completion(self, messages):
        try:
            # Try newer client.chat.completions.create format
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
                return completion.choices[0].message.content
            except (AttributeError, TypeError):
                # Fall back to older ChatCompletion.create format
                completion = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
                return completion.choices[0].message.content
        except Exception as e:
            print(f"Error in OpenAI API call: {str(e)}")
            # Return a fallback response that can be properly parsed
            return "{'error': 'API call failed'}"
    
class Claude:
    def __init__(self, model, api_key, temperature=0):
        self.Claude_url = "https://api.anthropic.com/v1"
        self.Claude_api_key = api_key
        self.model = model
        self.temperature = temperature

    @backoff.on_exception(backoff.expo, (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.RequestException), max_tries=5, factor=2, max_time=60)
    def create_chat_completion(self, messages):
        # convert messages to string
        formatted_string = "\n\n{}: {}\n\nAssistant: ".format("Human" if messages[0]["role"] == "user" else "Assistant", messages[0]["content"])
        url = f"{self.Claude_url}/complete"
        headers = {
            "accept": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.Claude_api_key,
            "Content-Type": "application/json"
        }
        
        # Add your implementation here
        # This is placeholder code and needs to be completed
        try:
            response = requests.post(
                url,
                headers=headers,
                json={
                    "prompt": formatted_string,
                    "model": self.model,
                    "temperature": self.temperature,
                    "max_tokens_to_sample": 1000
                }
            )
            response.raise_for_status()
            return response.json()["completion"]
        except Exception as e:
            print(f"Error in Claude API call: {str(e)}")
            return "{'error': 'API call failed'}"