# ─────────────────────────────────────────
# Stage 1: Base image
# ─────────────────────────────────────────

# Start from official Python image (slim = smaller size)
FROM python:3.11-slim

# ─────────────────────────────────────────
# Stage 2: Set working directory
# ─────────────────────────────────────────

# All commands from here run inside /app inside the container
WORKDIR /app

# ─────────────────────────────────────────
# Stage 3: Install dependencies
# ─────────────────────────────────────────

# Copy requirements FIRST (before copying your code)
# Why? Docker caches this layer — if requirements didn't change,
# it won't reinstall packages on every rebuild. Saves 2-3 minutes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────
# Stage 4: Copy your application code
# ─────────────────────────────────────────

# Copy everything from your project folder into /app
COPY . .

# ─────────────────────────────────────────
# Stage 5: Expose port and run
# ─────────────────────────────────────────

# Tell Docker this container listens on port 8000
EXPOSE 8000

# Command to start your FastAPI app
# 0.0.0.0 means "accept connections from outside the container"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]