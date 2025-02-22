generate_openapi_clients:
    uv run openapi-generator-cli generate -g python -i openapi/v1alpha.json -o generated/openapi_clients/v1alpha --package-name ballista.api.v1alpha
    cp -r generated/openapi_clients/v1alpha/ballista/api/ src/ballista/

generate:
    just generate_openapi_clients

clean:
    rm -rf generated/openapi_clients