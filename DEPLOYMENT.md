# Deployment Guide

This document provides instructions for deploying the Meraki Pi-hole Sync application.

## Docker

The easiest way to deploy the application is using Docker.

1.  Create a `.env` file from the `.env.example` file and fill in your actual values:
    ```bash
    cp .env.example .env
    ```

2.  Run the application using Docker Compose:
    ```bash
    docker-compose up --build -d
    ```

The application will be available at `http://localhost:24653`.

## Terraform

The application can also be deployed using Terraform. The Terraform configuration is located in the `terraform` directory.

1.  Initialize Terraform:
    ```bash
    terraform init
    ```

2.  Create a `terraform.tfvars` file and fill in your actual values.

3.  Apply the Terraform configuration:
    ```bash
    terraform apply
    ```
