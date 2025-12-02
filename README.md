# PSD to PNG Converter

## Быстрый запуск с Docker Compose:
```bash
docker-compose up -d --build
```

## Запуск в Kubernetes (k3s/minikube):

1. Соберите и опубликуйте Docker-образ в свой реестр, либо используйте docker-compose для локального теста.
```bash
docker build -t registry.domain.name/psd-converter:v0.0.1 .

docker push registry.domain.name/psd-converter:v0.0.1
```

2. Примените манифесты из папки `k8s`:
```bash
kubectl apply -k k8s/overlays/docker-desktop
# или для production:
kubectl apply -k k8s/overlays/production
```

## Описание
- Для production-окружения настройте свой ingress и image в kustomization.yaml.
