import json, re, threading
import rclpy, requests
from rclpy.node import Node
from std_msgs.msg import String

class ServerBridge(Node):
    def __init__(self):
        super().__init__('server_bridge')
        self.create_subscription(String, 'llm_request', self.request_callback, 10)
        self.publisher_ = self.create_publisher(String, 'llm_response', 10)
        self.get_logger().info('Server Bridge ready.')

    def request_callback(self, msg):
        # Don't block the executor: do the LLM work in a thread
        threading.Thread(target=self.handle, args=(msg.data,), daemon=True).start()

    def publish(self, text):
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        if text:
            out = String(); out.data = text
            self.publisher_.publish(out)

    def handle(self, prompt):
        payload = {
            "model": "qwen3:1.7b",
            "prompt": prompt,
            "system": "You are a voice assistant. Reply in one to three short "
                      "sentences of plain spoken English. No markdown, no lists.",
            "stream": True,
            "think": False,          # use "/no_think" in the prompt on older Ollama
            "keep_alive": "30m",
            "options": {"num_predict": 150, "num_ctx": 2048},
        }
        buf = ""
        try:
            with requests.post('http://localhost:11434/api/generate',
                               json=payload, stream=True, timeout=120) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    buf += chunk.get("response", "")
                    # Emit each complete sentence as soon as it exists
                    while (m := re.match(r'(.*?[.!?])\s+', buf, re.S)):
                        self.publish(m.group(1))
                        buf = buf[m.end():]
                    if chunk.get("done"):
                        break
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f'Ollama error: {e}')
            self.publish("Sorry, I couldn't reach the language model.")
        self.publish(buf)  # whatever is left

def main(args=None):
    rclpy.init(args=args)
    node = ServerBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()