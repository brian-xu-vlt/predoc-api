import json
import os
import re
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("MOCK_PORT", "4010"))
STEP_SECONDS = float(os.environ.get("MOCK_STEP_SECONDS", "3"))
EXAMPLES = json.loads((Path(__file__).parent / "examples.json").read_text())

MOCK_FACESHEET_CONFIG_ID = "00000000-0000-4000-8000-00000000fac5"
REQUIRED_REQUEST_FIELDS = [
    "releaseToOrgName",
    "releaseToProviderName",
    "previousProviders",
    "reasonForRequest",
    "requestingProviderEmail",
    "firstName",
    "lastName",
    "dateOfBirth",
    "phoneNumber",
    "patientAddress",
    "patientGender",
]
REQUEST_STAGES =["OPEN", "IN_PROGRESS", "COMPLETED"]
RETRIEVAL_STAGES = [("Processing", "PROCESSING", False), ("Completed", "COMPLETED", True)]
UPLOAD_STAGES = ["IDENTIFYING", "PROCESSING", "READY_TO_VALIDATE", "VALIDATING", "VALIDATED"]

lock = threading.Lock()
record_requests = {}
retrievals = {}
uploads = {}
webhook_configurations = {}
webhook_deliveries = []


def stage(created_at, stages):
    elapsed_steps = int((time.time() - created_at) / STEP_SECONDS)
    return stages[min(elapsed_steps, len(stages) - 1)]


def deliver_webhooks(*, event_type, payload, delay_steps):
    def send():
        with lock:
            configurations = [c for c in webhook_configurations.values() if c["eventType"] == event_type]
        for configuration in configurations:
            headers = {"Content-Type": "application/json"}
            headers.update({header["key"]: header["value"] for header in configuration.get("customHeaders", [])})
            body = json.dumps({"eventType": event_type, "occurredAt": time.time(), **payload}).encode()
            request = urllib.request.Request(configuration["url"], data=body, headers=headers, method="POST")
            try:
                urllib.request.urlopen(request, timeout=5)
                print(f"[mock] webhook {event_type} -> {configuration['url']}")
            except Exception as error:
                print(f"[mock] webhook {event_type} failed: {error}")

    threading.Timer(delay_steps * STEP_SECONDS, send).start()


def example_for(method, path):
    for example in EXAMPLES:
        pattern = "^" + re.sub(r":[A-Za-z]+", "[^/]+", example["path"]) + "$"
        if example["method"] == method and re.match(pattern, path):
            return example["status"], example["body"]
    return 404, {"message": f"no mock for {method} {path}"}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if "application/json" in (self.headers.get("Content-Type") or ""):
            return json.loads(raw or b"{}")
        return {}

    def handle_any(self, method):
        path = self.path.split("?")[0]
        body = self.read_body()

        if path == "/_mock/webhook-sink":
            if method == "POST":
                webhook_deliveries.append({"headers": dict(self.headers), "body": body})
                return self.send_json(200, {"received": True})
            return self.send_json(200, webhook_deliveries)

        if path == "/api/v1/auth/token" and method == "POST":
            return self.send_json(200, {"access_token": f"mock-token-{uuid.uuid4()}"})

        if not (self.headers.get("Authorization") or "").startswith("Bearer mock-token-"):
            return self.send_json(401, {"message": "Unauthorized"})

        if path in ("/api/v2/requests", "/api/v1/requests") and method == "POST":
            errors = [f"{field} is required" for field in REQUIRED_REQUEST_FIELDS if field not in body]
            if not re.fullmatch(r"\d{10}", str(body.get("phoneNumber", ""))):
                errors.append("phoneNumber must be 10 digits")
            if errors:
                return self.send_json(400, {"statusCode": 400, "message": errors})
            facesheet_config_ids = [body.get("facesheetConfigId"), *(body.get("facesheetConfigIds") or [])]
            facesheet_config_ids = [config_id for config_id in facesheet_config_ids if config_id]
            if body.get("sendHieRequest") and not facesheet_config_ids:
                return self.send_json(
                    400,
                    {"statusCode": 400, "message": "'facesheetConfigId(s)' must not be empty for the HIE retrieval method"},
                )
            if any(config_id != MOCK_FACESHEET_CONFIG_ID for config_id in facesheet_config_ids):
                return self.send_json(400, {"statusCode": 400, "message": f"Unknown facesheet config: {facesheet_config_ids}"})
            patient_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
            retrieval_ids = [str(uuid.uuid4()) for _ in body.get("previousProviders", [])]
            now = time.time()
            with lock:
                record_requests[request_id] = {"patientId": patient_id, "createdAt": now, "body": body}
                for retrieval_id in retrieval_ids:
                    retrievals[retrieval_id] = {"patientId": patient_id, "requestId": request_id, "createdAt": now}
            deliver_webhooks(
                event_type="REQUEST_COMPLETE",
                payload={"partnerPatientId": patient_id, "requestId": request_id},
                delay_steps=len(REQUEST_STAGES) - 1,
            )
            for retrieval_id in retrieval_ids:
                deliver_webhooks(
                    event_type="RETRIEVAL_COMPLETE",
                    payload={"partnerPatientId": patient_id, "requestId": request_id, "retrievalId": retrieval_id},
                    delay_steps=len(RETRIEVAL_STAGES) - 1,
                )
            return self.send_json(
                201,
                {
                    "partnerPatientId": patient_id,
                    "requestId": request_id,
                    "message": "Patient created successfully",
                    "previousProviderRetrievals": [{"id": retrieval_id} for retrieval_id in retrieval_ids],
                    "referenceId": body.get("referenceId"),
                },
            )

        match = re.match(r"^/api/v1/patients/([^/]+)/requests$", path)
        if match and method == "GET":
            patient_id = match.group(1)
            with lock:
                patient_requests = [(rid, r) for rid, r in record_requests.items() if r["patientId"] == patient_id]
            if not patient_requests:
                return self.send_json(404, {"message": "Patient not found"})
            return self.send_json(
                200,
                {
                    "partnerPatientId": patient_id,
                    "crrRequests": [
                        {
                            "crrId": request_id,
                            "requestReason": "Information Gathering",
                            "cumulativeRequestStatus": {stage(request["createdAt"], REQUEST_STAGES): 1},
                        }
                        for request_id, request in patient_requests
                    ],
                },
            )

        match = re.match(r"^/api/v1/retrievals/previous-providers/([^/]+)(/close)?$", path)
        if match:
            retrieval = retrievals.get(match.group(1))
            if retrieval is None:
                return self.send_json(404, {"message": "Retrieval not found"})
            status, status_group, can_close = stage(retrieval["createdAt"], RETRIEVAL_STAGES)
            if match.group(2) and method == "POST":
                if not can_close:
                    return self.send_json(409, {"message": "Retrieval cannot be closed yet"})
                retrieval["closed"] = True
            if retrieval.get("closed"):
                status, status_group, can_close = "Closed", "CLOSED", False
            return self.send_json(
                200,
                {
                    "retrievalId": match.group(1),
                    "partnerPatientId": retrieval["patientId"],
                    "requestId": retrieval["requestId"],
                    "status": status,
                    "statusGroup": status_group,
                    "canClose": can_close,
                },
            )

        if path == "/api/v1/records/upload/anonymous" and method == "POST":
            upload_id = str(uuid.uuid4())
            uploads[upload_id] = time.time()
            deliver_webhooks(
                event_type="ANONYMOUS_RECORD_UPLOAD_COMPLETED",
                payload={"recordUploadId": upload_id},
                delay_steps=len(UPLOAD_STAGES) - 1,
            )
            return self.send_json(201, {"recordUploadId": upload_id, "status": UPLOAD_STAGES[0], "message": "Upload received"})

        match = re.match(r"^/api/v1/records/uploads/([^/]+)/status$", path)
        if match and method == "GET":
            created_at = uploads.get(match.group(1))
            if created_at is None:
                return self.send_json(404, {"message": "Upload not found"})
            _, example = example_for("GET", path)
            return self.send_json(200, {**example, "recordUploadId": match.group(1), "status": stage(created_at, UPLOAD_STAGES)})

        if path == "/api/v1/requests/facesheet-configs" and method == "GET":
            return self.send_json(
                200,
                {"facesheetConfigs": [{"facesheetId": MOCK_FACESHEET_CONFIG_ID, "facesheetName": "Mock clinical facesheet"}]},
            )

        if path == "/api/v1/events":
            if method == "POST":
                configuration_id = str(uuid.uuid4())
                webhook_configurations[configuration_id] = {
                    "configurationId": configuration_id,
                    "eventType": body.get("eventType"),
                    "serviceName": body.get("serviceName"),
                    "url": body.get("webhookUri"),
                    "notificationEmail": body.get("notificationEmail"),
                    "isActive": True,
                    "customHeaders": body.get("customHeaders", []),
                }
                return self.send_json(201, webhook_configurations[configuration_id])
            return self.send_json(200, list(webhook_configurations.values()))

        match = re.match(r"^/api/v1/events/([^/]+)$", path)
        if match and method == "DELETE":
            webhook_configurations.pop(match.group(1), None)
            return self.send_json(200, {"configurationId": match.group(1)})

        status, example = example_for(method, path)
        return self.send_json(status, example)

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PATCH(self):
        self.handle_any("PATCH")

    def do_DELETE(self):
        self.handle_any("DELETE")


print(f"[mock] Predoc mock on http://localhost:{PORT}/api (status step: {STEP_SECONDS}s)")
ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()
