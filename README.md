# Medium Chat Bot

a simple chat bot that uses the OpenAI API to generate responses to user input.

## Requirements

- Internet connection
- Docker and Docker Compose installed
- OpenAI API key
- Telegram bot token

## Deployment on Local

1. Clone the repository
2. Copy the `.env.example` file to `.env` and fill in the required variables

    Note: When using Docker-Compose, the Redis database's host is `redis` that points to the Redis container.

3. Use the following command to setup the containers and start the application:

```bash
docker-compose up -d
```

4. Enjoy your chat bot!

## About Automatic Deployment on this respository

This repository is automatically deployed on Aliyun Severless App Engine (SAE) using the following steps:
1. When a commit is pushed to the `main` branch, the `docker-publish.yml` workflow is triggered, then the code is built into a Docker image and pushed to the GitHub Container Registry.
2. After that, the `alibaba.yml` workflow is triggered, would have a 15-minute delay to avoid some errors, and then the Docker image is pulled from the GitHub Container Registry and deployed to the Aliyun SAE.