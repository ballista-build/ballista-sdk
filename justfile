uv := require("uv")

[private]
default:
    just --list

# Run tests
test_units path=".":
    uv run coverage run -m pytest -m unit -s -vvvv {{ path }}
test path=".":
    uv run coverage run -m pytest -s -vvvv {{ path }}

kind_cluster_name := "ballista-test"
kind_cluster_version := "1.34"

# Needs kind and kubectl to work
_start_kubernetes_test_cluster: && _load_kubernetes_test_cluster_yaml
    kind create cluster --name {{ kind_cluster_name }} --kubeconfig {{ kind_cluster_name }}.kubeconfig --image kindest/node:v1.34.11@sha256:44e222ee2132dab25ff87301682f89eb82c7880ea3a1bf543bfe9708fd08d67d --wait 5m

_load_kubernetes_test_cluster_yaml:
    kubectl --kubeconfig {{ kind_cluster_name }}.kubeconfig apply -f test/adapters/kubernetes_test_cluster.yaml
    kubectl --kubeconfig {{ kind_cluster_name }}.kubeconfig wait --all-namespaces --for=condition=ready pod -l 'app.kubernetes.io/managed-by=Ballista' --timeout 1m

_stop_kubernetes_test_cluster:
    kind delete cluster --name {{ kind_cluster_name }} --kubeconfig {{ kind_cluster_name }}.kubeconfig
    rm {{ kind_cluster_name }}.kubeconfig

# Generate and report coverage
coverage: && coverage_report
    -uv run coverage run -m pytest

coverage_report:
    uv run coverage report -m
