FROM python:3.11

WORKDIR /app
COPY . /app

# Install libpq-dev
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=5s --retries=3 CMD python health_check.py

CMD ["uwsgi", "--ini", "hosting/uwsgi.ini"]