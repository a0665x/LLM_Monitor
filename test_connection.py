import time
import threading
from gradio_client import Client

def trigger_stream():
    print("Connecting to Gradio app...")
    try:
        client = Client("http://127.0.0.1:7860")
        print("Connected.")
        # We can't easily consume the stream via client without a prediction call.
        # But the app loads stream_camera on load.
        # Just connecting might not be enough if it's a generator outputting to an Image component.
        # However, Gradio usually starts the generator when the page loads.
        # The Client API interacts with endpoints.
        
        # Let's try to call analyze_once to see if it works
        print("Calling analyze_once...")
        result = client.predict(api_name="/analyze_once")
        print("Result:", result)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    trigger_stream()
