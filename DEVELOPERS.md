# Developer Documentation

This document provides instructions for setting up a development environment for the Meraki Pi-hole Sync application.

## Prerequisites

*   Docker
*   Docker Compose
*   Poetry

## Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/meraki-pihole-sync.git
    cd meraki-pihole-sync
    ```

2.  Install the dependencies using Poetry:
    ```bash
    poetry install
    ```

3.  Create a `.env` file from the `.env.example` file and fill in your actual values:
    ```bash
    cp .env.example .env
    ```

4.  Run the application using Docker Compose:
    ```bash
    docker-compose up --build
    ```

The application will be available at `http://localhost:24653`.

## Running Tests

To run the tests, use the following command:

```bash
poetry run pytest
```
