FROM ros:humble-ros-base

RUN apt-get update && apt-get install -y python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --default-timeout=120 --retries 10 requests piper-tts

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
 && echo "[ -f /ros2_ws/install/setup.bash ] && source /ros2_ws/install/setup.bash" >> /root/.bashrc \
 && echo "cd /ros2_ws" >> /root/.bashrc