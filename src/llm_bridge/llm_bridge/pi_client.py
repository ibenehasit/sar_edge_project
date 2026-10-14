import queue
import struct
import subprocess
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray


class PiClient(Node):
    def __init__(self):
        super().__init__('pi_client')
        self.publisher_ = self.create_publisher(String, 'llm_request', 10)
        self.subscription = self.create_subscription(
            UInt8MultiArray, 'llm_audio_response', self.audio_callback, 10)

        self.play_q = queue.Queue()
        threading.Thread(target=self.player, daemon=True).start()

        self.get_logger().info('Pi Client ready. Type your message and press Enter.')

    def send_request(self, text):
        msg = String()
        msg.data = text
        self.publisher_.publish(msg)
        self.get_logger().info(f'>>> Sending: {text}')

    def audio_callback(self, msg):
        data = bytes(msg.data)
        if len(data) <= 4:
            return
        rate = struct.unpack('<I', data[:4])[0]   # header added by the server
        self.play_q.put((rate, data[4:]))         # return immediately

    def player(self):
        # Plays chunks one at a time, in arrival order
        while True:
            rate, pcm = self.play_q.get()
            proc = subprocess.Popen(
                ['aplay', '-r', str(rate), '-f', 'S16_LE', '-t', 'raw', '-c', '1'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            proc.communicate(input=pcm)


def main(args=None):
    rclpy.init(args=args)
    node = PiClient()

    def input_loop():
        while rclpy.ok():
            try:
                user_input = input("Enter message: ")
                if user_input.lower() == 'exit':
                    rclpy.shutdown()   # lets spin() return so the program exits
                    break
                node.send_request(user_input)
            except EOFError:
                break

    threading.Thread(target=input_loop, daemon=True).start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()