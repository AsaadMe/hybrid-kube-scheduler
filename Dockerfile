FROM python:3.9-slim

WORKDIR /code
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip uninstall opencv-python -y
RUN pip install opencv-python-headless
COPY hybridscheduler kub-objects/iperf3.yaml ./

CMD python scheduler.py