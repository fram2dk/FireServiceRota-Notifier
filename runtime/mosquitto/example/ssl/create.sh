#!/bin/bash
openssl genrsa -out client.key 2048
openssl req -new -out client.csr -key client.key
openssl x509 -req -in client.csr -CA ./CA/ca.crt -CAkey ./CA/ca.key -CAcreateserial -out client.crt -days 4900
