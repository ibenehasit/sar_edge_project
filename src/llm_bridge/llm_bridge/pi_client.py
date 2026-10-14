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
            UInt8MultiArray,
            'llm_audio_response',
            self.audio_callback,
            10)
        self.get_logger().info('Pi Client ready. Type your message and press Enter.')

    def audio_callback(self, msg):
        # Convert the byte array back to bytes
        raw_audio = bytes(msg.data)
        
        # Pipe directly to aplay
        # Piper's en_GB-alan-medium outputs 22050 Hz, mono, signed 16-bit LE
        process = subprocess.Popen(
            ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-c', '1'],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        process.communicate(input=raw_audio)

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