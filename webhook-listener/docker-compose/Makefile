.PHONY: certs clean-certs clean-data clean

certs:
	mkcert -cert-file localhost-cert.pem -key-file localhost-key.pem localhost webhook-listener localhost 127.0.0.1 ::1

clean-certs:
	rm -f localhost-cert.pem localhost-key.pem

clean-data:
	sudo rm -rf mlflow-data

clean: clean-certs clean-data
