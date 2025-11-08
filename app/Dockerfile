# Dockerfile for our Flask application

# We are about to turn a folder of Python files into a single, runnable artifact
# that behaves the same on our laptop, on a cloud VM, or inside a Kubernetes
# cluster. The instructions below build that artifact layer by layer, starting
# from a bare-bones Linux image and ending with our own code spinning under
# Gunicorn. 

# ============================================================================
# 📦 BASE IMAGE
# ============================================================================

# Every container begins as a copy of some other image. We want one that
# already has Python 3.11 installed, but we do not want the extra weight of
# compilers, man pages, or other tools we will never touch. The official
# python:3.11-slim image gives us exactly that, a stripped-down Debian base
# with Python ready to go. 
FROM python:3.11-slim

# ============================================================================
# 🏷️ METADATA
# ============================================================================

# Labels do not change how the image runs, yet they are handy when we have
# dozens of images floating around a registry and we need to remember who
# built what and why.
LABEL maintainer="danieljbf02@gmail.com"
LABEL description="Self-healing Flask app for K8s demo"

# ============================================================================
# 📂 WORKING DIRECTORY
# ============================================================================

# Here, we create and move into the /app directory. From this point on, every
# command will assume that we are working inside this folder, just as if we had 
# run `cd /app` in the terminal.
WORKDIR /app

# ============================================================================
# ⚙️ INSTALLING DEPENDENCIES
# ============================================================================

# When we build a Docker image, we are essentially stacking a series of layers on 
# top of each other. Every instruction in the Dockerfile that can change the 
# filesystem (`COPY`, `RUN`, `ADD`, etc.) creates a new layer, and once a layer is 
# built, it becomes immutable. This means that if even a single byte changes in 
# one layer, Docker has to rebuild that layer and every layer that comes after 
# it from scratch. This is why the order of instructions in a Dockerfile has 
# such a big impact on how fast our builds run. We want to structure the file so 
# that layers that rarely change come first, and layers that change often come 
# later. This helps Docker reuse as many cached layers as possible between builds.
# For a Python project, our dependencies usually change far less often than our 
# application code. The set of third-party packages listed in the 
# `requirements.txt` file might stay the same for weeks, while the source code 
# changes every day, so it makes sense to install the dependencies in their own 
# layer before we copy the rest of the project. As long as the `requirements.txt` 
# file does not change, Docker will simply reuse the pre-built layer that already 
# contains the installed packages, turning a multi-minute `pip install` into a 
# sub-second cache hit.
COPY requirements.txt .

# Now that the `requirements.txt` file is inside the image, we can finally ask pip
# to fetch and install all the dependencies we need to run our application. We add 
# the `--no-cache-dir` flag so that pip does not save temporary installation files 
# (called 'wheels') inside the container. Those files are useful on a developer 
# laptop where the same package might be reinstalled many times, but inside a Docker 
# image, they are single-use garbage that only bloats the layer. Dropping them keeps 
# the final image smaller and avoids shipping useless bytes to production.
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# 💻 APPLICATION CODE
# ============================================================================

# When we copy `main.py` (or any other file) into the image, Docker keeps track of
# its contents using a unique cryptographic hash. If we then change even a single 
# byte in that file, the hash changes too, and so Docker knows it needs to 
# rebuild this layer and any layers that come after it. The good news is that the 
# `pip install` layer that contains all the installed dependencies stays the same, 
# so Docker can pull it straight from the cache instead of having to reinstall 
# everything again.
COPY main.py .

# ============================================================================
# 🔒 SECURITY
# ============================================================================

# If we run our container using the default `root` user, any vulnerability in our 
# application could be exploited by an attacker to gain system-wide privileges, 
# potentially letting them install malware or access sensitive data on the host 
# machine. To prevent this from happening, we follow the principle of least 
# privilege by creating a special user called `appuser` that has just enough 
# rights to run our application and nothing else. For more information on this,
# see https://docs.docker.com/build/building/best-practices/#user
RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

# This command switches the running context inside the container from the
# default `root` user to our newly created `appuser`.
USER appuser

# ============================================================================
# 🌐 RUNTIME CONFIGURATION
# ============================================================================

# The `EXPOSE` instruction does not actually publish the port or make it accessible
# outside the container. It simply tells other developers and the runtime environment
# (like Docker or Kubernetes), which ports the container will listen on at runtime.
# In a way, it is really just a note or a declaration of intent, like another piece 
# of metadata we attach to the image. To actually publish the port and make it available 
# on the host machine, we must use the `-p` or `--publish` flag when running the container 
# (e.g., docker run -p 5000:5000 app) or define port mappings in an orchestrator like 
# Kubernetes or Docker Compose.
EXPOSE 5000

# We define environment variables here so our application can start with default 
# settings already in place, even if we forget to explicitly set them during 
# deployment. These default values are embedded directly into the image layer, but 
# we can easily override them at runtime (without rebuilding the image) using the 
# `docker run -e` flag, a Docker Compose file, or a Kubernetes Deployment manifest.
ENV APP_VERSION=1.0.0
ENV APP_ENV=production
ENV PORT=5000

# ============================================================================
# ❤️ HEALTH CHECK
# ============================================================================

# This adds a simple built-in health check directly into the image. Docker will 
# periodically send a request to our /health endpoint to make sure the app is healthy 
# and ready to serve traffic. Even though Kubernetes usually does this for us, having 
# one here helps keep the image self-contained and reusable. It also allows us to check 
# the status of our container at any time using `docker ps` or `docker inspect`.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# ============================================================================
# 🚀 THE STARTUP COMMAND
# ============================================================================

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "main:app"]