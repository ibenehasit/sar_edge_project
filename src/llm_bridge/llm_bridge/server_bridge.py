import json
import re
import struct
import threading

import requests
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray
from piper import PiperVoice

PIPER_MODEL = "/ros2_ws/voices/en_GB-alba-medium.onnx"


class ServerBridge(Node):
    def __init__(self):
        super().__init__('server_bridge')          # must come first

        self.voice = PiperVoice.load(PIPER_MODEL)
        self.tts_lock = threading.Lock()           # keeps sentences in order

        self.create_subscription(String, 'llm_request', self.request_callback, 10)
        self.text_pub = self.create_publisher(String, 'llm_response', 10)
        self.audio_pub = self.create_publisher(UInt8MultiArray, 'llm_audio_response', 10)

        self.get_logger().info('Server Bridge ready.')

        #giving the bot memory of the convo
        self.history = []              # list of {"role": ..., "content": ...}
        self.history_lock = threading.Lock()
        self.MAX_TURNS = 8             # keep the last 6 exchanges

    def request_callback(self, msg):
        # Don't block the executor: do the LLM work in a thread
        threading.Thread(target=self.process_request,
                         args=(msg.data,), daemon=True).start()

    def publish(self, text):
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        if not text:
            return

        self.get_logger().info(f'Speaking: "{text}"')

        # Also publish the text, handy for debugging with `ros2 topic echo`
        t = String()
        t.data = text
        self.text_pub.publish(t)

        # Synthesize and send audio, one message per Piper chunk
        with self.tts_lock:
            for chunk in self.voice.synthesize(text):
                out = UInt8MultiArray()
                out.data = struct.pack('<I', chunk.sample_rate) + chunk.audio_int16_bytes
                self.audio_pub.publish(out)

    def process_request(self, prompt):
        with self.history_lock:
            self.history.append({"role": "user", "content": prompt})
            messages = [{"role": "system",
                        "content": "You are a voice assistant. Reply in one to three short "
                                    "sentences of plain spoken English. No markdown, no lists."}
                        ] + self.history[-self.MAX_TURNS * 2:]

        payload = {
            "model": "qwen3:1.7b",
            "messages": messages,
            "stream": True,
            "think": False,
            "keep_alive": "30m",
            "options": {"num_predict": 150, "num_ctx": 2048},
        }
        buf = ""
        full_reply = ""
        try:
            with requests.post('http://localhost:11434/api/chat',
                            json=payload, stream=True, timeout=120) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    piece = chunk.get("message", {}).get("content", "")   # note: different field
                    buf += piece
                    full_reply += piece
                    while (m := re.match(r'(.*?[.!?])\s+', buf, re.S)):
                        self.publish(m.group(1))
                        buf = buf[m.end():]
                    if chunk.get("done"):
                        break
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f'Ollama error: {e}')
            self.publish("Sorry, I couldn't reach the language model.")
        self.publish(buf)

        if full_reply.strip():
            with self.history_lock:
                self.history.append({"role": "assistant", "content": full_reply.strip()})


def main(args=None):
    rclpy.init(args=args)
    node = ServerBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()