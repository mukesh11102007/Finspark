FROM python:3.10-slim

WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files (including DB scripts, model files, and HTML)
COPY . .

# Expose the Flask port
EXPOSE 5000

# The app uses adhoc SSL, so it needs pyopenssl installed
CMD ["python", "app.py"]
