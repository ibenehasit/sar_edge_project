import json
import re
import struct
import threading

import chromadb
import requests
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray
from piper import PiperVoice

PIPER_MODEL = "/ros2_ws/voices/en_GB-alba-medium.onnx"
DB_PATH = "/ros2_ws/rag_db"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"    # must match the model used in ingest.py
LLM_MODEL = "qwen3:1.7b"


def embed(texts):
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": EMBED_MODEL, "input": texts}, timeout=120)
    r.raise_for_status()
    return r.json()["embeddings"]


class FallacyBot(Node):
    def __init__(self):
        super().__init__('fallacy_bot')            # must come first

        self.voice = PiperVoice.load(PIPER_MODEL)
        self.tts_lock = threading.Lock()

        # Open the database that ingest.py built (errors clearly if it's missing)
        client = chromadb.PersistentClient(path=DB_PATH)
        self.col = client.get_collection("fallacies")

        self.create_subscription(String, 'llm_request', self.request_callback, 10)
        self.text_pub = self.create_publisher(String, 'llm_response', 10)
        self.audio_pub = self.create_publisher(UInt8MultiArray, 'llm_audio_response', 10)

        self.get_logger().info(
            f'Fallacy bot ready ({self.col.count()} entries in knowledge base).')

    def request_callback(self, msg):
        self.get_logger().info(f'Received argument: "{msg.data}"')
        threading.Thread(target=self.process_request,
                         args=(msg.data,), daemon=True).start()

    def publish(self, text):
        """Publishes the text, then speaks it."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        if not text:
            return
        self.get_logger().info(f'Replying: "{text}"')

        t = String()
        t.data = text
        self.text_pub.publish(t)

        with self.tts_lock:
            for chunk in self.voice.synthesize(text):
                out = UInt8MultiArray()
                out.data = struct.pack('<I', chunk.sample_rate) + chunk.audio_int16_bytes
                self.audio_pub.publish(out)

    def retrieve(self, argument, k=4):
        res = self.col.query(query_embeddings=embed([argument]), n_results=k)
        return res["documents"][0]

    def process_request(self, argument):
        try:
            refs = "\n\n".join(self.retrieve(argument))
            self.get_logger().info(f'Retrieved:\n{refs}')   # handy for judging retrieval

            prompt = (
                "You check arguments for logical fallacies.\n"
                "Use ONLY the reference entries below. If none of them clearly applies, "
                "answer with no fallacy.\n\n"
                f"REFERENCE ENTRIES:\n{refs}\n\nARGUMENT:\n{argument}"
            )
            payload = {
                "model": LLM_MODEL, "prompt": prompt, "stream": False,
                "think": False, "keep_alive": "30m",
                "format": {"type": "object",
                           "properties": {"fallacy": {"type": ["string", "null"]},
                                          "reason": {"type": "string"}},
                           "required": ["fallacy", "reason"]},
                "options": {"temperature": 0, "num_ctx": 4096},
            }
            r = requests.post(f"{OLLAMA}/api/generate", json=payload, timeout=120)
            r.raise_for_status()
            verdict = json.loads(r.json()["response"])

            if verdict.get("fallacy"):
                self.publish(f"Fallacy: {verdict['fallacy']}. {verdict['reason']}")
            else:
                self.publish(f"No fallacy found. {verdict['reason']}")

        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
            self.get_logger().error(f'Pipeline error: {e}')
            self.publish("Sorry, something went wrong checking that argument.")


def main(args=None):
    rclpy.init(args=args)
    node = FallacyBot()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()