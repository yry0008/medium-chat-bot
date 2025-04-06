FROM --platform=amd64 python:3.12-alpine

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python", "main.py" ]
# CMD [ "python", "main.py" ]