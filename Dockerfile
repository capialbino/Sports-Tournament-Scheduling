FROM minizinc/minizinc:2.9.5

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and build tools
RUN apt-get update && apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        python3-dev \
        build-essential \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
WORKDIR /cdmo
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Upgrade pip tools
RUN pip install --upgrade pip setuptools wheel

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY ./source ./source
COPY ./res ./res
COPY solution_checker.py .

CMD ["sh"]
