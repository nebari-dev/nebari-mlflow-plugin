#!/bin/sh
uvicorn listener:app --reload --ssl-keyfile ./localhost-key.pem --ssl-certfile ./localhost-cert.pem --host 0.0.0.0 --log-level debug