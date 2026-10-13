import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class PiClient(Node):
    def __init__(self):
        super().__init__('pi_client')
        # Publisher for sending requests to the server
        self.publisher_ = self.create_publisher(String, 'llm_request', 10)
        # Subscriber for receiving answers from the server
        self.subscription = self.create_subscription(
            String,
            'llm_response',
            self.response_callback,
            10)
        self.get_logger().info('Pi Client ready. Type your message and press Enter.')

    def response_callback(self, msg):
        # This prints the answer received from the server
        self.get_logger().info(f'<<< Server says: {msg.data}')

    def send_request(self, text):
        # This creates a message and publishes it
        msg = String()
        msg.data = text
        self.publisher_.publish(msg)
        self.get_logger().info(f'>>> Sending: {text}')

def main(args=None):
    rclpy.init(args=args)
    node = PiClient()
    
    # We use a separate thread or just loop to handle input without blocking ROS spinning
    # For simplicity, we'll use a loop with rclpy.spin_once
    import threading
    
    def input_loop():
        while rclpy.ok():
            try:
                user_input = input("Enter message: ")
                if user_input.lower() == 'exit':
                    break
                node.send_request(user_input)
            except EOFError:
                break

    # Start input thread
    thread = threading.Thread(target=input_loop, daemon=True)
    thread.start()
    
    # Spin the ROS node to handle incoming responses
    rclpy.spin(node)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()