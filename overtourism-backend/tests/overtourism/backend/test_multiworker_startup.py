# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from overtourism.dt_manager.manager.manager import Manager
from overtourism.dt_manager.stores.config import StoreConfig


def test_crud_bootstrap_completes_before_multiple_workers_start(tmp_path) -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    database_path = tmp_path / "overtourism.sqlite"
    database_url = f"sqlite:///{database_path}"

    manager = Manager(StoreConfig("sql", {"url": database_url}))
    manager.problem_manager.create_problem(
        "fazzon_base_problem",
        "fazzon",
        name="Fazzon",
    )
    manager.scenario_manager.create_scenario(
        "fazzon_base_scenario",
        "fazzon",
        name="Base scenario",
    )
    manager.proposal_manager.create_proposal(
        "fazzon_base_proposal",
        "fazzon_base_problem",
        name="Fazzon proposal",
        status="draft",
    )
    manager.scenario_manager.create_scenario(
        "fazzon_a1_no_cap",
        "fazzon",
        name="A1 without cap",
    )
    manager.store.engine.dispose()

    class ModelApiHandler(BaseHTTPRequestHandler):
        registry_requests = 0
        registry_lock = threading.Lock()
        registry_barrier = threading.Barrier(2)

        def log_message(self, _format: str, *args: object) -> None:
            pass

        def _respond(self, payload: object) -> None:
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/models":
                with self.registry_lock:
                    type(self).registry_requests += 1
                try:
                    self.registry_barrier.wait(timeout=1)
                except threading.BrokenBarrierError:
                    pass
                self._respond([{"key": "fazzon", "title": "Fazzon"}])
                return
            if self.path == "/ready":
                self._respond({"status": "ready"})
                return
            self.send_error(404)

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self._respond({})

    model_api = ThreadingHTTPServer(("127.0.0.1", 0), ModelApiHandler)
    model_thread = threading.Thread(target=model_api.serve_forever, daemon=True)
    model_thread.start()

    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        api_port = port_socket.getsockname()[1]

    environment = os.environ.copy()
    environment.update(
        {
            "OVERTOURISM_DATABASE": database_url,
            "MODEL_BACKEND_URL": f"http://127.0.0.1:{model_api.server_port}",
            "DT_OVERTURISM_STANDALONE_MODE": "true",
            "AUTH_ENABLED": "false",
            "CORS_ALLOWED_ORIGINS": "*",
        }
    )
    environment.pop("LOG_CONFIG_FILE", None)
    environment.pop("PYTHONPATH", None)

    try:
        bootstrap = subprocess.run(
            [sys.executable, "-m", "overtourism.overtourism.bootstrap"],
            cwd=backend_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr

        log_path = tmp_path / "uvicorn.log"
        with log_path.open("w+", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "overtourism.overtourism.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--workers",
                    "2",
                    "--log-level",
                    "info",
                ],
                cwd=backend_dir,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{api_port}/health/live",
                            timeout=0.5,
                        ) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError, OSError):
                        time.sleep(0.1)
                else:
                    raise AssertionError("CRUD API did not become ready")

                with urlopen(
                    f"http://127.0.0.1:{api_port}/api/fazzon/proposals/"
                    "fazzon_base_proposal",
                    timeout=2,
                ) as response:
                    proposal = json.load(response)
                time.sleep(0.5)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=8)
                log_file.flush()
                log_file.seek(0)
                server_logs = log_file.read()
    finally:
        model_api.shutdown()
        model_api.server_close()
        model_thread.join(timeout=2)

    assert ModelApiHandler.registry_requests == 1
    assert "fazzon_a1_no_cap" in proposal["related_scenario_ids"]
    assert server_logs.count("Application startup complete.") == 2
    assert "IntegrityError" not in server_logs
