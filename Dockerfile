# Use the official Python image as the base image
FROM python:3.10-slim

ENV PYTHONPATH="/app"

RUN apt-get update && apt-get install -y net-tools

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file to install dependencies
COPY requirements.txt /app/

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app's code
COPY . /app/

# Expose the Streamlit port (default is 8501)
EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "web_app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
