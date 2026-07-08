# Use the official Python lightweight image
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True

# Set the working directory
ENV APP_HOME /app
WORKDIR $APP_HOME

# Copy local code to the container image
COPY . ./

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run sets the PORT environment variable. We default to 8080 if not set.
# Run the web service on container startup using uvicorn.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
