import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import requests

class ServerBridge(Node):
    def __init__(self):
        super().__init__('server_bridge')
        # Subscribe to requests from the Pi
        self.subscription = self.create_subscription(
            String,
            'llm_request',
            self.request_callback,
            10)
        # Publisher to send answers back to the Pi
        self.publisher_ = self.create_publisher(String, 'llm_response', 10)
        self.get_logger().info('Server Bridge ready. Waiting for requests...')

    def request_callback(self, msg):
        user_text = msg.data
        self.get_logger().info(f'Received request: "{user_text}"')
        
        # Call the Ollama API
        answer = self.call_ollama(user_text)
        
        # Publish the answer back to the Pi
        response_msg = String()
        response_msg.data = answer
        self.publisher_.publish(response_msg)
        self.get_logger().info(f'Sent response: "{answer[:50]}..."')

    def call_ollama(self, prompt):
        # This is the local API endpoint for Ollama
        url = 'http://localhost:11434/api/generate'
        
        # The request payload (data) we send to Ollama
        payload = {
            "model": "qwen3:1.7b",
            "prompt": prompt,
            "stream": False  # We want the full answer at once
        }
        
        try:
            # Send a POST request to Ollama
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()  # Check for HTTP errors
            
            # Extract the generated text from the JSON response
            result = response.json()
            return result.get("response", "No response generated.")
            
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f'Ollama API error: {e}')
            return "Error: Could not connect to the LLM server."

def main(args=None):
    rclpy.init(args=args)
    node = ServerBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()