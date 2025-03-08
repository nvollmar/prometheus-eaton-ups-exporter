FROM python:3.13.2-alpine3.21

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    rm requirements.txt && \
    mkdir etc

# Copy the application code
COPY prometheus_eaton_ups_exporter prometheus_eaton_ups_exporter
COPY prometheus_eaton_ups_exporter.py .
COPY requirements.txt .
COPY .pyre_configuration .

CMD ["python", "./prometheus_eaton_ups_exporter.py", "-k", "-v", "-c", "/usr/src/app/etc/config.json", "-w", "0.0.0.0:9795"]
