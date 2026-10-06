.PHONY: help mocks data features train risk allocate api web test

help:
	@echo "Targets:"
	@echo "  mocks     generate mock artifacts in artifacts/mock/ (works now)"
	@echo "  data      step 2: ingest, label, clean"
	@echo "  features  step 3: features, PCA, split"
	@echo "  train     step 4: models, calibration, SHAP"
	@echo "  risk      step 5: revenue at risk, forecast, segments"
	@echo "  allocate  step 6: budget allocation"
	@echo "  api       step 7: run FastAPI"
	@echo "  web       step 7: run React dashboard"
	@echo "  test      run pytest"

mocks:
	python scripts/make_mocks.py

data:
	PYTHONPATH=src python -m churn.pipeline.run_data

features:
	PYTHONPATH=src python -m churn.pipeline.run_features

train:
	PYTHONPATH=src python -m churn.pipeline.run_train

risk:
	PYTHONPATH=src python -m churn.pipeline.run_risk

allocate:
	PYTHONPATH=src python -m churn.pipeline.run_allocate

api:
	PYTHONPATH=src python -m uvicorn api.app:app --port 8000

web:
	cd frontend && npm install && npm run dev

test:
	python -m pytest
