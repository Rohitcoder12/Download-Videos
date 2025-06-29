# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (like ffmpeg)
# We can run apt-get here because we are building the image as root
RUN apt-get update && apt-get install -y ffmpeg

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Command to run the application
CMD ["python", "main.py"]