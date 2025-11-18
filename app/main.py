import os
import sys
import socket
from datetime import datetime
from flask import Flask, jsonify

# ============================================================================
# ⚙️ APPLICATION SETUP AND CONFIGURATION
# ============================================================================

# The first thing we need to do is create a Flask application instance. This
# instance will serve as the main entry point for our application and is
# responsible for handling incoming requests and routing them to the
# appropriate view functions. In Flask, view functions are defined using the
# @app.route() decorator, which registers them to a specific URL path. These
# functions behave very much like a controller in a MVC architecture, handling
# the business logic and returning a response to the client.
app = Flask(__name__)

# In cloud-native environments like Kubernetes, configuration (ConfigMaps) and
# sensitive data (Secrets) are decoupled from the application image. These
# values are typically injected as environment variables at deployment time,
# allowing settings to be changed without needing to rebuild or redeploy the
# application code. The application retrieves these values using standard OS
# functions (e.g., `os.getenv()`)
APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
APP_ENV = os.getenv('APP_ENV', 'development')

# We will now record the exact time the application process started, so we can
# later calculate and report its uptime for monitoring and debugging purposes.
START_TIME = datetime.now()

# ============================================================================
# 🛠️ HELPER FUNCTIONS
# ============================================================================

def get_pod_info() -> dict:
    """
    Retrieves identifying network information for the current container
    instance (Pod).

    When this application runs inside a Kubernetes cluster, this function
    identifies the specific **Pod** (the smallest deployable unit) handling the
    request. This information is extremely useful for debugging and tracing
    requests when running multiple replicas behind a load balancer.

    The OS hostname typically corresponds to the **Pod Name**, and the IP is
    the **Pod IP** (which is internal to the cluster network).

    :return: A dictionary containing the hostname (Pod Name) and IP address of
             the container.
    :rtype: dict
    """
    # socket.gethostname() resolves the hostname of the current machine.
    hostname = socket.gethostname()
    # socket.gethostbyname() resolves the IP address bound to that hostname.
    ip_address = socket.gethostbyname(hostname)

    return {
        'hostname': hostname,
        'ip': ip_address
    }


def get_uptime() -> str:
    """
    Calculates the uptime (age) of the current container instance (Pod).

    This metric is used by monitoring systems to identify when a container was
    last restarted by Kubernetes, whether intentionally (e.g., deployment) or
    unintentionally (e.g., a crash detected by the liveness probe). Every time
    the container restarts, this uptime counter resets to zero, so a
    consistently low uptime can be a sign of frequent crashes or service
    disruptions (a "crash loop").

    :return: A formatted string representing the uptime (e.g., "1 day,
             2:03:45").
    :rtype: str
    """
    # Calculate the timedelta between now and the recorded start time.
    uptime = datetime.now() - START_TIME
    # We convert the timedelta to a string and strip the sub-second precision
    # for a clean, concise output (H:MM:SS format).
    return str(uptime).split('.')[0]


# ============================================================================
# 🌐 ROUTES AND ENDPOINTS
# ============================================================================

@app.route('/')
def home():
    """
    The root or informational endpoint (`/`).

    This endpoint is the primary way to check if the service is reachable and
    to inspect its current state. In this example, The response includes
    configuration details (version, environment) and runtime information from
    the host container (Pod Name, IP, uptime), allowing clients to quickly
    identify the specific backend replica serving the request behind a load
    balancer.

    :return: A JSON response with a snapshot of the application's current
             state.
    """
    pod_info = get_pod_info()

    return jsonify({
        'message': 'Self-Healing Web App Status',
        'version': APP_VERSION,
        'environment': APP_ENV,
        'pod': {
            'hostname': pod_info['hostname'],
            'ip': pod_info['ip'],
            'uptime': get_uptime()
        },
        # Always include a timestamp for traceability.
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health')
def health():
    """
    The health check endpoint (`/health`).

    This endpoint is one of the most important pieces of code in any
    cloud-native application. Modern container orchestrators such as Kubernetes
    and ECS rely heavily on health checks to manage the entire lifecycle of a
    container instance (Pod) and to determine whether it can handle live
    traffic. There are different types of health checks, but the most common
    ones are liveness and readiness probes:

    1. **Liveness Probe (Is the app alive and healthy?)**
       Kubernetes periodically checks this probe to ensure the application
       process is running and has not become stuck, frozen, or entered an
       unrecoverable state (such as a deadlock, starvation, or infinite loop). 
       If the liveness probe fails (e.g., by returning a non-200 status code or
       timing out), the orchestrator assumes the application is broken and
       automatically **restarts the container**, hoping to bring the
       application back to a working state.

    2. **Readiness Probe (Is the app ready to serve traffic?)**
       This check tells the load balancer whether the service is capable of
       handling new requests **right now**. During startup, or while the
       application waits for external resources (like initializing a database
       connection pool), the readiness probe can temporarily return a non-200
       response. This signals to the load balancer that the Pod should be
       **removed from the service pool** until the check passes, at which point
       the Pod is automatically reinstated.

    For very simple, standalone services that have no external dependencies (no
    database, no external APIs to wait for), a single endpoint like this one
    can safely serve both the liveness and readiness checks by just returning a
    **200 OK** status as long as the application process is running. However,
    for anything even moderately complex, it is usually better to split them
    into separate, dedicated endpoints (e.g., `/livez` and `/readyz`). The "z"
    at the end is a long-standing convention used to distinguish endpoints
    intended for **programmatic access** by monitoring tools and service
    orchestrators, as opposed to those intended for **end users**.

    :return: A JSON response with status 'healthy' and HTTP status code 200.
    """
    # In this example, we provide a simple "always OK" health check. In a real
    # system, we would add logic here to check external dependencies, like
    # pinging the database or checking queue depth. If any check fails, we
    # would return a 503 Service Unavailable. Do not add any heavy logic that
    # might slow down the response, as this check is typically performed many
    # times per minute.
    # try:
    #     db_connection.ping()
    # except:
    #     return jsonify({'status': 'unhealthy'}), 503

    return jsonify({
        'status': 'healthy',
        'uptime': get_uptime()
    }), 200


@app.route('/crash')
def crash():
    """
    A deliberate fault-injection endpoint (`/crash`).

    NOTE: This endpoint is solely for **TESTING** the self-healing capabilities
    of the orchestration environment (e.g., Kubernetes). It must **NEVER** be
    included in production code.

    When executed, the following steps occur:
    1. A Flask response object is created using `jsonify()`, but not yet sent
       to the client. In the WSGI model, data is only transmitted once the
       route returns the response.
    2. Immediately afterward, the process calls `os._exit(1)`.
       This halts the interpreter *instantly*, bypassing all cleanup, buffer
       flushing, and finally/teardown handlers.
    3. Because the process terminates before the response is returned, the WSGI
       server never has a chance to write any bytes to the network socket.
       Therefore, the client **will not receive** the JSON message or even the
       HTTP headers.
    4. The orchestrator (e.g., Kubernetes) detects the non-zero exit code (1)
       and, depending on its restart policy, replaces the failed container with
       a brand new one.

    :return: (Unreachable) A JSON response describing the crash.
    """
    # The first thing we need to do is create a Flask response object. This
    # prepares the data (the JSON payload) that would normally be sent back to
    # the client if the process did not crash.
    response = jsonify({
        'message': 'Initiating fatal crash to test Liveness Probe recovery...',
        'pod': get_pod_info()['hostname']
    })

    # We then call `os._exit(1)` to immediately terminate the process.
    # `os._exit(1)` performs a low-level exit (a syscall) that bypasses ALL
    # standard Python cleanup routines (e.g., `finally` blocks, `atexit`
    # handlers, I/O buffer flushing). This makes it a much better choice than
    # `sys.exit(1)` or `exit(1)` for simulating a true, immediate,
    # unrecoverable crash (like a segmentation fault or an out-of-memory
    # error).
    os._exit(1)

    # NOTE: We deliberately AVOID the `@after_this_request` decorator, which
    # would schedule the exit *after* the response is sent. That would simulate
    # a graceful shutdown, not a hard crash.

    # This return statement is UNREACHABLE due to os._exit(1) above.
    return response


@app.route('/metrics')
def metrics():
    """
    A basic observability endpoint (`/metrics`).

    In production, this endpoint is often exposed on a separate port (e.g.,
    8080) to keep it isolated from regular user traffic. A monitoring system,
    such as **Prometheus**, then connects to this port at scheduled intervals
    (e.g., every 5 minutes) to scrape, or collect, metrics from the
    application. After the metrics are collected, they are typically stored in
    a dedicated time-series database and later used for a wide variety of
    tasks, including:
    * **Monitoring & Dashboards:** Tracking Key Performance Indicators (KPIs)
      such as request rates, response times, and cache hit ratios.
    * **Alerting:** Automatically notifying engineers when metrics (e.g., high
      latency, error rates) exceed predefined thresholds.
    * **Autoscaling:** Providing data (e.g., CPU usage) for Horizontal Pod
      Autoscalers (HPA) to dynamically manage resource allocation.

    :returns: A JSON response containing basic application metrics (uptime,
              version, environment).
    """
    return jsonify({
        'uptime_seconds': (datetime.now() - START_TIME).total_seconds(),
        'version': APP_VERSION,
        'environment': APP_ENV
    })


# ============================================================================
# ⛔ ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """
    Handles HTTP 404 (Not Found) errors gracefully.

    When a client requests an endpoint that doesn't exist, we intercept the
    default Flask error and return a standardized JSON response with the
    appropriate 404 status code. This is a standard practice for any API that
    handles client requests.

    :param error: The underlying 404 error object.
    :return: A JSON response with a 404 status code.
    """
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist on this service'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """
    Handles HTTP 500 (Internal Server Error) errors gracefully.

    This handler catches uncaught exceptions that occur within the application
    logic. Instead of exposing raw stack traces, we return a generic, safe JSON
    response to the client with the 500 status code, logging the details
    internally for debugging.

    NOTE: Detailed error information should be logged, not returned to the
    client.

    :param error: The underlying 500 error object.
    :return: A JSON response with a 500 status code.
    """
    # In a real app, we would log the full traceback here before returning the
    # generic error. logging.exception() is used inside an exception handler to
    # log the full traceback of the most recently caught exception (the 500
    # error).
    # logging.exception("An uncaught exception occurred while processing a request.")

    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected condition was encountered by the server.'
    }), 500


# ============================================================================
# 🚀 APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # This is the main block where the application process officially begins.

    # ------------------------------------------------------------------------
    # Configuration Check
    # ------------------------------------------------------------------------
    # We retrieve the port from an environment variable (standard for
    # containerization) or default to the common Flask port 5000.
    port = int(os.getenv('PORT', 5000))

    print(f"--- Starting Microservice Application ---")
    print(f"Version: {APP_VERSION}")
    print(f"Environment: {APP_ENV}")
    print(f"Serving on Port: {port}")
    print(f"Current Hostname (Pod Name): {socket.gethostname()}")

    # ------------------------------------------------------------------------
    # Start Flask Server
    # ------------------------------------------------------------------------
    app.run(
        # The host must be set to '0.0.0.0' inside a container. This makes the
        # service available on all network interfaces, allowing the container
        # runtime and Kubernetes networking layer to access it.
        host='0.0.0.0',
        port=port,
        # Debug mode must be disabled in production to avoid exposing sensitive
        # system information (stack traces) to unauthorized users.
        debug=(APP_ENV == 'development')
    )