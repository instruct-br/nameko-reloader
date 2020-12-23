# nameko-reloader

Extensão do Nameko, que adiciona o recurso de `hot-reload` quando detecta alterações no arquivo do serviço nameko.

## Executando

Inicie seus serviços passando a flag `--reload`, como no exemplo abaixo:

```py
nameko_reloader run service.service_a service.service_b --reload
```
