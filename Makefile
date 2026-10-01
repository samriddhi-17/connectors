.PHONY: compose-up compose-down kind-up kind-down seed alert lint test

compose-up:            ## Local demo via podman compose
	scripts/deploy-compose.ps1

compose-down:
	podman compose down

kind-up:               ## Kubernetes demo via kind + podman
	scripts/deploy-kind.sh

kind-down:
	kind delete cluster --name connects

seed:                  ## POST a demo alert to the OpenSRE bridge
	scripts/seed-alert.sh

test:
	cd backend && python -m pytest -q

lint:
	cd backend && python -m ruff check app tests 2>/dev/null || echo "ruff not installed (optional)"
	cd frontend && npm run build