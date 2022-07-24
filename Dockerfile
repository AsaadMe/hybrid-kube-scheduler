FROM python:3.9-slim

WORKDIR /code
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY hybridscheduler kub-objects/iperf3.yaml ./

CMD python scheduler.py