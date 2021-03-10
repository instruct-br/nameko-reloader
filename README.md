# nameko-reloader

Extension for [Nameko](https://www.nameko.io/), that implements the _hot-reload_ feature, when detects changes in service file.

## Usage

Start your services using `nameko_reloader`, and passing the `--reload` option:

```sh
nameko_reloader run service.service_a service.service_b --reload
```
