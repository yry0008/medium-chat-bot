FROM --platform=amd64 python:3.12-alpine


ENV TELEGRAM_TOKEN 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ

ENV OPENAI_API_KEY sk-114514
ENV OPENAI_API_BASE https://api.openai.com/v1
ENV OPENAI_DEFAULT_MODEL gpt-4o
ENV OPENAI_VISION_MODEL gpt-4o

ENV HISTORY_DAYS 7
ENV HISTORY_MAX_MESSAGES 10

ENV SYSTEM_PROMPT "You are a helpful assistant. You can answer questions, provide information, and assist with various tasks. Please respond to the user's queries in a friendly and informative manner."
ENV MAX_COMPLETION_TOKENS 512

ENV REDIS_HOST redis
ENV REDIS_PORT 6379
ENV REDIS_DB 0
ENV REDIS_USERNAME null 
ENV REDIS_PASSWORD null

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python", "main.py" ]
# CMD [ "python", "main.py" ]